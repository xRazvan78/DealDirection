import { CanActivateFn } from '@angular/router';

// Task 14: redirect to /login when there is no token. Not attached to any route yet.
export const authGuard: CanActivateFn = () => true;
