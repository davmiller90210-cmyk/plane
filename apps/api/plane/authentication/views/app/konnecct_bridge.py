# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""Konnecct CRM bridge: establish a Plane session from a short-lived HS256 JWT minted by crm-server."""

import os
import uuid

import jwt
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from plane.authentication.utils.login import user_login
from plane.authentication.utils.user_auth_workflow import post_user_auth_workflow
from plane.db.models import Profile, User, Workspace, WorkspaceMember


class KonnecctBridgeView(APIView):
    """
    POST with Authorization: Bearer <jwt>
    JWT payload (HS256, KONNECCT_BRIDGE_SECRET): email, workspace_slug, first_name, last_name, clerk_user_id, exp
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
        first_name = (payload.get("first_name") or "").strip()
        last_name = (payload.get("last_name") or "").strip()

        if not email or not workspace_slug:
            return Response(
                {"error": "Bridge token must include email and workspace_slug"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_email(email)
        except ValidationError:
            return Response({"error": "Invalid email in bridge token"}, status=status.HTTP_400_BAD_REQUEST)

        workspace = Workspace.objects.filter(slug=workspace_slug).first()
        if workspace is None:
            return Response(
                {
                    "error": "PLANE_WORKSPACE_NOT_FOUND",
                    "detail": f"No Plane workspace with slug {workspace_slug!r}. Create it or set PLANE_KONNECCT_WORKSPACE_SLUG.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        user = User.objects.filter(email=email).first()
        is_signup = False
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

        profile, _ = Profile.objects.get_or_create(user=user)
        profile.is_onboarded = True
        profile.last_workspace_id = workspace.id
        profile.save()

        if not WorkspaceMember.objects.filter(
            workspace=workspace,
            member=user,
            deleted_at__isnull=True,
        ).exists():
            WorkspaceMember.objects.create(
                workspace=workspace,
                member=user,
                role=20,
            )

        post_user_auth_workflow(user=user, is_signup=is_signup, request=request)
        user_login(request=request, user=user, is_app=True)

        return Response({"ok": True}, status=status.HTTP_200_OK)
