import { TestBed } from '@angular/core/testing';
import { SwUpdate, VersionEvent } from '@angular/service-worker';
import { Subject } from 'rxjs';
import { reloadOnNewVersion } from './updates';

const version = { hash: 'abc' };

describe('reloadOnNewVersion', () => {
  let versionUpdates: Subject<VersionEvent>;
  let checkForUpdate: ReturnType<typeof vi.fn>;
  let reload: () => void;

  function start(isEnabled = true): void {
    versionUpdates = new Subject();
    checkForUpdate = vi.fn().mockResolvedValue(false);
    reload = vi.fn();
    TestBed.configureTestingModule({
      providers: [
        { provide: SwUpdate, useValue: { isEnabled, versionUpdates, checkForUpdate } },
      ],
    });
    TestBed.runInInjectionContext(() => reloadOnNewVersion(reload));
  }

  it('reloads once a new version is ready', () => {
    start();

    versionUpdates.next({
      type: 'VERSION_READY',
      currentVersion: version,
      latestVersion: version,
    });

    expect(reload).toHaveBeenCalledOnce();
  });

  it('does not reload while a new version is only being downloaded', () => {
    start();

    versionUpdates.next({ type: 'VERSION_DETECTED', version });

    expect(reload).not.toHaveBeenCalled();
  });

  it('checks for a new version when returning to the app', () => {
    start();

    document.dispatchEvent(new Event('visibilitychange'));

    expect(checkForUpdate).toHaveBeenCalled();
  });

  it('does nothing when the service worker is off', () => {
    start(false);

    versionUpdates.next({
      type: 'VERSION_READY',
      currentVersion: version,
      latestVersion: version,
    });
    document.dispatchEvent(new Event('visibilitychange'));

    expect(reload).not.toHaveBeenCalled();
    expect(checkForUpdate).not.toHaveBeenCalled();
  });
});
