import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { Observable, finalize } from 'rxjs';
import { AuthService } from '../core/auth';
import { AuthResponse } from '../core/models';
import { ro } from '../shared/ro';

// Only for new accounts: older passwords must still be able to log in.
const PASSWORD_RULE = /^(?=.*[0-9])(?=.*[^\p{L}\p{N}\s]).{6,}$/su;

@Component({
  imports: [ReactiveFormsModule],
  selector: 'app-login',
  styleUrl: './login.scss',
  templateUrl: './login.html',
})
export class Login {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  protected readonly ro = ro;
  protected readonly registering = signal(false);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly form = inject(FormBuilder).nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', Validators.required],
  });

  protected submit(): void {
    const details = this.form.getRawValue();
    if (this.form.invalid || (this.registering() && !PASSWORD_RULE.test(details.password))) {
      this.error.set(ro.login.invalid);
      return;
    }
    this.enter(this.registering() ? this.auth.register(details) : this.auth.login(details));
  }

  protected demo(): void {
    this.enter(this.auth.demo());
  }

  protected switchMode(): void {
    this.registering.update((value) => !value);
    this.error.set(null);
  }

  private enter(request: Observable<AuthResponse>): void {
    this.busy.set(true);
    this.error.set(null);
    request.pipe(finalize(() => this.busy.set(false))).subscribe({
      next: () => void this.router.navigateByUrl('/browse'),
      error: (error: HttpErrorResponse) => this.error.set(this.messageFor(error.status)),
    });
  }

  private messageFor(status: number): string {
    if (status === 401) {
      return ro.login.wrongDetails;
    }
    if (status === 409) {
      return ro.login.emailTaken;
    }
    return status === 422 ? ro.login.invalid : ro.login.failed;
  }
}
