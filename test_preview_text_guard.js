const assert = require('assert');
const fs = require('fs');
const path = require('path');

const previewPath = path.join(__dirname, 'app', 'templates', 'preview.html');
const source = fs.readFileSync(previewPath, 'utf8');

function expectRegex(regex, msg) {
  assert(regex.test(source), msg);
}

function run() {
  // Garante que o horário principal usa baseline alphabetic com y calculado por métricas (evita clipping superior)
  expectRegex(
    /const\s+ascent\s*=\s*Math\.ceil\(metrics\.actualBoundingBoxAscent\s*\|\|\s*12\);[\s\S]*?const\s+mainClockY\s*=\s*2\s*\+\s*ascent;[\s\S]*?drawMonoText\(clockText,\s*3,\s*mainClockY,\s*\{[\s\S]*?baseline:\s*'alphabetic'/m,
    'Relógio principal deve usar baseline alphabetic com y calculado por ascent para evitar clipping'
  );

  // Garante que drawMonoText aceita baseline configurável
  expectRegex(
    /const\s*\{[\s\S]*?baseline\s*=\s*'alphabetic'[\s\S]*?\}\s*=\s*opts;/m,
    'drawMonoText deve manter opção baseline configurável'
  );

  // Garante capa quadrada usando targetSize x targetSize
  expectRegex(
    /ctx\.drawImage\(off,\s*sx,\s*sy,\s*sw,\s*sh,\s*dstX,\s*dstY,\s*targetSize,\s*targetSize\)/m,
    'Capa deve ser desenhada em área quadrada (targetSize x targetSize)'
  );

  // Garante centralização vertical da capa na altura 32
  expectRegex(
    /const\s+dstY\s*=\s*Math\.floor\(\(CANVAS_HEIGHT\s*-\s*targetSize\)\s*\/\s*2\);/m,
    'Capa deve ser centralizada verticalmente no painel'
  );

  console.log('✓ Guard test: regras de visibilidade de texto e capa quadrada presentes no preview.');
}

run();
