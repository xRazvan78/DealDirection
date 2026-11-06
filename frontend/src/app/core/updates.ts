import { inject } from '@angular/core';
import { SwUpdate } from '@angular/service-worker';
import { filter, fromEvent } from 'rxjs';

// The service worker keeps serving the build it cached, so without this a phone
// stays on the old app after a new build. A phone also rarely reloads the page,
// so returning to the app checks for a new version too.
export function reloadOnNewVersion(reload = () => location.reload()): void {
  const updates = inject(SwUpdate);
  if (!updates.isEnabled) {
    return;
  }
  updates.versionUpdates
    .pipe(filter((event) => event.type === 'VERSION_READY'))
    .subscribe(() => reload());
  fromEvent(document, 'visibilitychange')
    .pipe(filter(() => document.visibilityState === 'visible'))
    .subscribe(() => void updates.checkForUpdate().catch(() => undefined));
}
