import { create } from 'qrcode';

export interface QrDrawing {
  size: number;
  path: string;
}

// An SVG path for a code, so it stays sharp at any size and needs no canvas.
export function qrCode(text: string): QrDrawing {
  const { size, data } = create(text, { errorCorrectionLevel: 'M' }).modules;
  let path = '';
  for (let row = 0; row < size; row++) {
    for (let column = 0; column < size; column++) {
      if (data[row * size + column]) {
        path += `M${column} ${row}h1v1h-1z`;
      }
    }
  }
  return { size, path };
}
