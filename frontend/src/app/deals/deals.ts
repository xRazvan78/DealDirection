import { Component } from '@angular/core';
import { ro } from '../shared/ro';

@Component({
  selector: 'app-deals',
  styleUrl: './deals.scss',
  templateUrl: './deals.html',
})
export class Deals {
  protected readonly ro = ro;
}
