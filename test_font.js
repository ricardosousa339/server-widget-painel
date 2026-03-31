const { createCanvas, registerFont } = require('canvas');
registerFont('assets/minecraftia.ttf', { family: 'Minecraftia' });
const canvas = createCanvas(64, 32);
const ctx = canvas.getContext('2d');
ctx.fillStyle = '#000';
ctx.fillRect(0,0,64,32);

ctx.font = '8px "Minecraftia"';
ctx.fillStyle = '#FFF';

ctx.textBaseline = 'bottom';
ctx.fillText('Test', 0, 13);
// Let's print out what rows have pixels
const data = ctx.getImageData(0,0,64,32).data;
for(let y=0; y<32; y++) {
  let hasPixel = false;
  for(let x=0; x<64; x++) {
    if(data[(y*64 + x)*4] > 0) hasPixel = true;
  }
  if(hasPixel) console.log('Row ' + y + ' has pixels');
}
