import { Component, input, output } from '@angular/core';
import { ReceiptReading } from '../core/models';
import { formatLei, formatQuantity, formatReceiptDate } from '../shared/format';
import { ro } from '../shared/ro';

// A receipt as it was read. While `deciding`, the client can accept or cancel it;
// otherwise it's only shown, for a list that already has its receipt.
@Component({
  selector: 'app-receipt-dialog',
  styleUrl: './receipt-dialog.scss',
  templateUrl: './receipt-dialog.html',
})
export class ReceiptDialog {
  readonly reading = input.required<ReceiptReading>();
  readonly deciding = input(false);
  readonly accepted = output();
  readonly dismissed = output();

  protected readonly ro = ro;
  protected readonly formatLei = formatLei;
  protected readonly formatQuantity = formatQuantity;
  protected readonly formatReceiptDate = formatReceiptDate;
}
