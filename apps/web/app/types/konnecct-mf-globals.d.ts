declare global {
  interface Window {
    __KONNECCT_PLANE_MF_HOST__?: boolean;
    __konnecctPlaneBootstrapPromise?: Promise<void>;
    __reactRouterDataRouter?: { navigate: (to: string | number, opts?: { replace?: boolean }) => void };
  }
}

export {};
