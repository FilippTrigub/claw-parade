#!/usr/bin/env node
/**
 * resize.js — Stage 1 of the clawimig pipeline
 *
 * Resizes a single image to Instagram-compatible dimensions using sharp.
 * Called per-file by process.py.
 *
 * Usage:
 *   node resize.js --input <path> --output <path> \
 *     --width <n> --height <n> \
 *     --fit <contain|cover|fill> \
 *     --bg <hex-or-css-color> \
 *     --format <jpeg|png|webp> \
 *     --quality <1-100>
 */

const sharp = require('sharp');
const path = require('path');

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i += 2) {
    const key = argv[i].replace(/^--/, '');
    args[key] = argv[i + 1];
  }
  return args;
}

function validateArgs(args) {
  const required = ['input', 'output', 'width', 'height', 'fit', 'bg', 'format', 'quality'];
  for (const key of required) {
    if (!args[key]) {
      console.error(`Missing required argument: --${key}`);
      process.exit(1);
    }
  }

  const validFit = ['contain', 'cover', 'fill'];
  if (!validFit.includes(args.fit)) {
    console.error(`Invalid --fit "${args.fit}". Must be one of: ${validFit.join(', ')}`);
    process.exit(1);
  }

  const validFormat = ['jpeg', 'png', 'webp'];
  if (!validFormat.includes(args.format)) {
    console.error(`Invalid --format "${args.format}". Must be one of: ${validFormat.join(', ')}`);
    process.exit(1);
  }

  const quality = parseInt(args.quality, 10);
  if (isNaN(quality) || quality < 1 || quality > 100) {
    console.error(`Invalid --quality "${args.quality}". Must be an integer between 1 and 100.`);
    process.exit(1);
  }

  return {
    input: args.input,
    output: args.output,
    width: parseInt(args.width, 10),
    height: parseInt(args.height, 10),
    fit: args.fit,
    bg: args.bg,
    format: args.format,
    quality,
  };
}

function parseColor(hex) {
  // Accept hex (#rrggbb or #rgb) or CSS named colors passed as-is to sharp
  if (hex.startsWith('#')) {
    const full = hex.length === 4
      ? '#' + hex[1] + hex[1] + hex[2] + hex[2] + hex[3] + hex[3]
      : hex;
    const r = parseInt(full.slice(1, 3), 16);
    const g = parseInt(full.slice(3, 5), 16);
    const b = parseInt(full.slice(5, 7), 16);
    return { r, g, b };
  }
  // Named color — pass as string, sharp accepts CSS color names
  return hex;
}

async function run() {
  const raw = parseArgs(process.argv);
  const opts = validateArgs(raw);
  const background = parseColor(opts.bg);

  let pipeline = sharp(opts.input).resize(opts.width, opts.height, {
    fit: opts.fit,
    background,
    withoutEnlargement: false,
  });

  // When fit=contain, add padding to fill the canvas
  if (opts.fit === 'contain') {
    pipeline = pipeline.extend({
      top: 0,
      bottom: 0,
      left: 0,
      right: 0,
      background,
    });
    // Re-resize to exact dimensions after extend (extend can add fractional pixels)
    pipeline = pipeline.resize(opts.width, opts.height, {
      fit: 'fill',
    });
  }

  switch (opts.format) {
    case 'jpeg':
      pipeline = pipeline.jpeg({ quality: opts.quality, mozjpeg: true });
      break;
    case 'png':
      pipeline = pipeline.png({ quality: opts.quality });
      break;
    case 'webp':
      pipeline = pipeline.webp({ quality: opts.quality });
      break;
  }

  await pipeline.toFile(opts.output);
  console.log(`resized: ${path.basename(opts.input)} → ${opts.width}x${opts.height} (${opts.format})`);
}

run().catch((err) => {
  console.error(`Error processing image: ${err.message}`);
  process.exit(1);
});
