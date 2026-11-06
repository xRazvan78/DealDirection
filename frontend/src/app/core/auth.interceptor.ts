import { HttpInterceptorFn } from '@angular/common/http';

// Task 14: send the token on API calls, and log out on a 401.
export const authInterceptor: HttpInterceptorFn = (request, next) => next(request);
