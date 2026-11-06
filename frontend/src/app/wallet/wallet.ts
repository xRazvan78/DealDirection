import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, inject, signal } from '@angular/core';
import { finalize, forkJoin } from 'rxjs';
import { ApiService } from '../core/api';
import { Reward, Voucher, Wallet as WalletData } from '../core/models';
import { qrCode } from '../shared/qr';
import { ro } from '../shared/ro';

// Called the Point Shop on screen. The route stays /wallet, matching the API.
@Component({
  imports: [DatePipe],
  selector: 'app-wallet',
  styleUrl: './wallet.scss',
  templateUrl: './wallet.html',
})
export class Wallet {
  private readonly api = inject(ApiService);

  protected readonly ro = ro;
  protected readonly wallet = signal<WalletData | null>(null);
  protected readonly rewards = signal<Reward[]>([]);
  protected readonly vouchers = signal<Voucher[]>([]);
  protected readonly loadFailed = signal(false);
  protected readonly redeemingId = signal<number | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly openVoucher = signal<Voucher | null>(null);
  protected readonly qr = computed(() => {
    const voucher = this.openVoucher();
    return voucher ? qrCode(voucher.code) : null;
  });

  constructor() {
    forkJoin({
      wallet: this.api.getWallet(),
      rewards: this.api.getRewards(),
      vouchers: this.api.getVouchers(),
    }).subscribe({
      next: ({ wallet, rewards, vouchers }) => {
        this.wallet.set(wallet);
        this.rewards.set(rewards);
        this.vouchers.set(vouchers);
      },
      error: () => this.loadFailed.set(true),
    });
  }

  protected pointsShort(reward: Reward): number {
    return Math.max(0, reward.cost - (this.wallet()?.balance ?? 0));
  }

  protected redeem(reward: Reward): void {
    if (this.redeemingId() !== null) {
      return;
    }
    this.redeemingId.set(reward.id);
    this.error.set(null);
    this.api
      .redeemReward(reward.id)
      .pipe(finalize(() => this.redeemingId.set(null)))
      .subscribe({
        next: (voucher) => {
          this.vouchers.update((vouchers) => [voucher, ...vouchers]);
          this.openVoucher.set(voucher);
          this.refreshBalance();
        },
        error: (error: HttpErrorResponse) =>
          this.error.set(error.status === 409 ? ro.wallet.notEnough : ro.wallet.redeemFailed),
      });
  }

  // The points are already spent here, so a failure must not look like a failed redeem.
  private refreshBalance(): void {
    this.api.getWallet().subscribe({
      next: (wallet) => this.wallet.set(wallet),
      error: () => undefined,
    });
  }
}
