# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""Konnecct CRM bridge: establish a Plane session from a short-lived HS256 JWT minted by crm-server."""

import os
import uuid

import jwt
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from plane.authentication.utils.login import user_login
from plane.authentication.utils.user_auth_workflow import post_user_auth_workflow
from plane.db.models import (
    DEFAULT_STATES,
    Profile,
    Project,
    ProjectIdentifier,
    ProjectMember,
    State,
    User,
    Workspace,
    WorkspaceMember,
)
from plane.utils.constants import RESTRICTED_WORKSPACE_SLUGS


def _normalize_workspace_role(raw) -> int:
    try:
        r = int(raw)
    except (TypeError, ValueError):
        return 15
    if r in (5, 15, 20):
        return r
    return 15


def _derive_project_identifier(workspace: Workspace) -> str:
    s = "".join(c for c in workspace.slug.upper() if c.isalnum())
    if len(s) < 2:
        s = "PR"
    base = s[:12]
    ident = base
    n = 0
    while Project.objects.filter(
        workspace=workspace, identifier=ident, deleted_at__isnull=True
    ).exists():
        n += 1
        suffix = str(n)
        ident = (base[: 12 - len(suffix)] + suffix)[:12]
    return ident


def _ensure_default_project(workspace: Workspace, user: User, member_role: int) -> None:
    existing = Project.objects.filter(workspace=workspace, deleted_at__isnull=True).first()
    if existing is not None:
        pm = ProjectMember.objects.filter(
            project=existing, member=user, deleted_at__isnull=True
        ).first()
        if pm is None:
            ProjectMember.objects.create(
                project=existing,
                member=user,
                role=member_role,
                workspace_id=workspace.id,
            )
        elif pm.role != member_role:
            pm.role = member_role
            pm.save(update_fields=["role"])
        return

    ident = _derive_project_identifier(workspace)
    project = Project(
        name=(workspace.name or workspace.slug)[:255],
        identifier=ident,
        workspace=workspace,
        module_view=True,
        cycle_view=True,
        issue_views_view=True,
    )
    project.save(created_by_id=user.id, disable_auto_set_user=True)
    ProjectIdentifier.objects.create(
        name=project.identifier, project=project, workspace_id=workspace.id
    )

    default_state_obj = None
    for sd in DEFAULT_STATES:
        st = State.all_state_objects.create(
            name=sd["name"],
            description="",
            color=sd["color"],
            sequence=sd["sequence"],
            group=sd["group"],
            default=bool(sd.get("default", False)),
            project=project,
        )
        st.save(created_by_id=user.id, disable_auto_set_user=True)
        if sd.get("default"):
            default_state_obj = st

    if default_state_obj is not None:
        project.default_state = default_state_obj
        project.save(update_fields=["default_state"])

    ProjectMember.objects.create(
        project=project,
        member=user,
        role=member_role,
        workspace_id=workspace.id,
    )


class KonnecctBridgeView(APIView):
    """
    POST with Authorization: Bearer <jwt>
    JWT payload (HS256, KONNECCT_BRIDGE_SECRET):
      email, workspace_slug, workspace_name?, workspace_role?, first_name, last_name, clerk_user_id?, exp
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        secret = os.environ.get("KONNECCT_BRIDGE_SECRET", "").strip()
        if not secret:
            return Response(
                {"error": "KONNECCT_BRIDGE_SECRET is not configured on Plane API"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return Response({"error": "Missing bearer token"}, status=status.HTTP_401_UNAUTHORIZED)

        token = auth.split(" ", 1)[1].strip()
        try:
            payload = jwt.decode(token, secret, algorithms=["HS256"])
        except jwt.PyJWTError:
            return Response({"error": "Invalid or expired bridge token"}, status=status.HTTP_401_UNAUTHORIZED)

        email = (payload.get("email") or "").strip().lower()
        workspace_slug = (payload.get("workspace_slug") or "").strip()
        workspace_name = (payload.get("workspace_name") or "").strip()
        workspace_role = _normalize_workspace_role(payload.get("workspace_role"))
        first_name = (payload.get("first_name") or "").strip()
        last_name = (payload.get("last_name") or "").strip()

        if not email or not workspace_slug:
            return Response(
                {"error": "Bridge token must include email and workspace_slug"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if workspace_slug in RESTRICTED_WORKSPACE_SLUGS:
            return Response(
                {"error": "Workspace slug is not allowed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_email(email)
        except ValidationError:
            return Response({"error": "Invalid email in bridge token"}, status=status.HTTP_400_BAD_REQUEST)

        is_signup = False
        try:
            with transaction.atomic():
                user = User.objects.filter(email=email).first()
                if user is None:
                    is_signup = True
                    user = User(
                        email=email,
                        username=uuid.uuid4().hex,
                        first_name=first_name,
                        last_name=last_name,
                        is_password_autoset=True,
                        is_email_verified=True,
                    )
                    user.set_password(uuid.uuid4().hex)
                    user.save()
                    Profile.objects.create(user=user)

                workspace = Workspace.objects.filter(
                    slug=workspace_slug, deleted_at__isnull=True
                ).first()

                if workspace is None:
                    display_name = (workspace_name or workspace_slug).strip()[:80] or workspace_slug
                    workspace = Workspace(
                        name=display_name,
                        slug=workspace_slug,
                        owner=user,
                    )
                    workspace.save(created_by_id=user.id, disable_auto_set_user=True)
                    WorkspaceMember.objects.create(
                        workspace=workspace,
                        member=user,
                        role=workspace_role,
                    )
                else:
                    wm = WorkspaceMember.objects.filter(
                        workspace=workspace,
                        member=user,
                        deleted_at__isnull=True,
                    ).first()
                    if wm is None:
                        WorkspaceMember.objects.create(
                            workspace=workspace,
                            member=user,
                            role=workspace_role,
                        )
                    elif wm.role != workspace_role:
                        wm.role = workspace_role
                        wm.save(update_fields=["role"])

                _ensure_default_project(workspace, user, workspace_role)

                profile, _ = Profile.objects.get_or_create(user=user)
                profile.is_onboarded = True
                profile.last_workspace_id = workspace.id
                profile.save()
        except Exception:
            return Response(
                {"error": "KONNECCT_BRIDGE_PROVISION_FAILED"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        post_user_auth_workflow(user=user, is_signup=is_signup, request=request)
        user_login(request=request, user=user, is_app=True)

        return Response({"ok": True}, status=status.HTTP_200_OK)
