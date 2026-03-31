const { createCanvas, registerFont } = require('canvas');
registerFont('assets/minecraftia.ttf', { family: 'Minecraftia' });
const canvas = createCanvas(64, 32);
const ctx = canvas.getContext('2d');
ctx.fillStyle = '#000';
ctx.fillRect(0,0,64,32);

ctx.font = '8px "Minecraftia"';
ctx.fillStyle = '#FFF';

ctx.textBaseline = 'top';
ctx.fillText('Test', 0, 4);
