declare module "workbox-window" {
  export class Workbox {
    constructor(scriptURL: string, options?: Record<string, unknown>);
    register(): Promise<ServiceWorkerRegistration>;
  }
}
