const assert = require('assert');
const { createCanvas, registerFont } = require('canvas');

registerFont('assets/minecraftia.ttf', { family: 'Minecraftia' });

const CANVAS_WIDTH = 64;
const CANVAS_HEIGHT = 32;
const CANVAS_FONT = '"Minecraftia", monospace';

function createCtx(w = CANVAS_WIDTH, h = CANVAS_HEIGHT) {
  const canvas = createCanvas(w, h);
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, w, h);
  return { canvas, ctx };
}

function drawMonoText(ctx, text, x, y, opts = {}) {
  const {
    color = '#f5f7ff',
    font = `8px ${CANVAS_FONT}`,
    clipWidth = null,
    outline = false,
    baseline = 'alphabetic',
  } = opts;

  ctx.save();
  ctx.font = font;
  ctx.textBaseline = baseline;
  ctx.textAlign = 'left';

  if (clipWidth != null) {
    ctx.beginPath();
    ctx.rect(x, -32, clipWidth, 96);
    ctx.clip();
  }

  const bx = Math.floor(x);
  const by = Math.floor(y);

  if (outline) {
    ctx.fillStyle = '#000';
    ctx.fillText(text, bx - 1, by);
    ctx.fillText(text, bx + 1, by);
    ctx.fillText(text, bx, by - 1);
    ctx.fillText(text, bx, by + 1);
  }

  ctx.fillStyle = color;
  ctx.fillText(text, bx, by);
  ctx.restore();
}

function drawClock(ctx, data) {
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);

  const clockText = data.time || '--:--';
  const clockFont = `16px ${CANVAS_FONT}`;
  ctx.save();
  ctx.font = clockFont;
  const metrics = ctx.measureText(clockText);
  ctx.restore();
  const ascent = Math.ceil(metrics.actualBoundingBoxAscent || 12);
  const mainClockY = 2 + ascent;

  drawMonoText(ctx, clockText, 3, mainClockY, {
    font: clockFont,
    clipWidth: CANVAS_WIDTH,
    outline: true,
    baseline: 'alphabetic',
  });

  const footerFont = `8px ${CANVAS_FONT}`;
  drawMonoText(ctx, (data.weekday || '---').toUpperCase(), 3, 29, {
    font: footerFont,
    clipWidth: 32,
  });
  drawMonoText(ctx, data.date || '--/--', 34, 29, {
    font: footerFont,
    clipWidth: 32,
  });
}

function decodeRgb565ToImageData(ctx, rgb565Buffer, w, h) {
  const imageData = ctx.createImageData(w, h);
  let p = 0;

  for (let i = 0; i < rgb565Buffer.length; i += 2) {
    const value = (rgb565Buffer[i] << 8) | rgb565Buffer[i + 1];
    const r = ((value >> 11) & 0x1f) * 255 / 31;
    const g = ((value >> 5) & 0x3f) * 255 / 63;
    const b = (value & 0x1f) * 255 / 31;

    imageData.data[p++] = r;
    imageData.data[p++] = g;
    imageData.data[p++] = b;
    imageData.data[p++] = 255;
  }

  return imageData;
}

function makeDummyRgb565(w, h) {
  const bytes = Buffer.alloc(w * h * 2);
  let p = 0;

  for (let y = 0; y < h; y += 1) {
    for (let x = 0; x < w; x += 1) {
      const r5 = Math.floor((x / (w - 1 || 1)) * 31);
      const g6 = Math.floor((y / (h - 1 || 1)) * 63);
      const b5 = 31 - r5;
      const value = (r5 << 11) | (g6 << 5) | b5;

      bytes[p++] = (value >> 8) & 0xff;
      bytes[p++] = value & 0xff;
    }
  }

  return bytes;
}

function drawCover(ctx, cover, targetSize = 24) {
  const w = cover.w || 32;
  const h = cover.h || 32;
  const imageData = decodeRgb565ToImageData(ctx, cover.data, w, h);

  const off = createCanvas(w, h);
  const offCtx = off.getContext('2d');
  offCtx.putImageData(imageData, 0, 0);

  const dstRatio = 1;
  const srcRatio = w / h;
  let sx = 0;
  let sy = 0;
  let sw = w;
  let sh = h;

  if (srcRatio > dstRatio) {
    sw = Math.round(h * dstRatio);
    sx = Math.floor((w - sw) / 2);
  } else if (srcRatio < dstRatio) {
    sh = Math.round(w / dstRatio);
    sy = Math.floor((h - sh) / 2);
  }

  const dstX = 0;
  const dstY = Math.floor((CANVAS_HEIGHT - targetSize) / 2);
  ctx.drawImage(off, sx, sy, sw, sh, dstX, dstY, targetSize, targetSize);
}

function getNonBlackBoundingBox(ctx, x0 = 0, y0 = 0, w = CANVAS_WIDTH, h = CANVAS_HEIGHT) {
  const { data } = ctx.getImageData(x0, y0, w, h);
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -1;
  let maxY = -1;

  for (let y = 0; y < h; y += 1) {
    for (let x = 0; x < w; x += 1) {
      const i = (y * w + x) * 4;
      const isNotBlack = data[i] > 0 || data[i + 1] > 0 || data[i + 2] > 0;
      if (!isNotBlack) continue;

      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
    }
  }

  if (maxX < 0 || maxY < 0) {
    return null;
  }

  return {
    minX,
    minY,
    maxX,
    maxY,
    width: maxX - minX + 1,
    height: maxY - minY + 1,
  };
}

function testClockTextFitsScreen() {
  // Canvas "alto" para detectar clipping potencial fora da área 32px
  const { ctx } = createCtx(CANVAS_WIDTH, 96);

  drawClock(ctx, {
    time: '17:49',
    weekday: 'TER',
    date: '31/03',
  });

  const visibleBox = getNonBlackBoundingBox(ctx, 0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);
  assert(visibleBox, 'Relógio não desenhou pixels visíveis no painel 64x32');

  const fullBox = getNonBlackBoundingBox(ctx, 0, 0, CANVAS_WIDTH, 96);
  assert(fullBox, 'Relógio não desenhou pixels no canvas completo');

  // Se tudo está visível no painel, o bbox "completo" deve estar dentro de 0..31 em Y.
  assert(
    fullBox.minY >= 0 && fullBox.maxY < CANVAS_HEIGHT,
    `Texto do relógio extrapola painel 64x32 (minY=${fullBox.minY}, maxY=${fullBox.maxY})`
  );

  console.log('✓ Relógio: texto dentro do painel 64x32 sem extrapolação vertical.');
}

function testCoverIsSquare() {
  const { ctx } = createCtx();

  const cover = {
    w: 16,
    h: 32,
    data: makeDummyRgb565(16, 32),
  };

  drawCover(ctx, cover, 26);

  const coverBox = getNonBlackBoundingBox(ctx, 0, 0, 26, CANVAS_HEIGHT);
  assert(coverBox, 'Capa não foi desenhada');

  assert.strictEqual(
    coverBox.width,
    26,
    `Largura da capa deveria ser 26px, mas foi ${coverBox.width}px`
  );
  assert.strictEqual(
    coverBox.height,
    26,
    `Altura da capa deveria ser 26px (quadrada), mas foi ${coverBox.height}px`
  );

  console.log('✓ Capa: renderização quadrada (26x26).');
}

function main() {
  testClockTextFitsScreen();
  testCoverIsSquare();
  console.log('\nOK: todos os testes de visibilidade de texto/capa passaram.');
}

main();
