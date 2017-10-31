
#
# This attempts to create art inspired by one of Andrew Covell's paintings
# I encountered at the Brewery Artwalk in LA on Oct 21, 2017.
#
# The painting has the following characteristics:
#
#   1. The image comprises many small tiled parallelograms which are painted
#      individually.
#   2. Color is applied by painting many small dots, not strokes, which layer
#      to create details and gradients.
#   3. Colors are chosen from a small palette. I estimate about a dozen
#      different colors per parallelogram tile.
#   4. Each tile has a 3D effect where the colors near the edges get lighter
#      or darker to help visually separate each tile.
#
# This can be applied to any image, but I find that simpler scenes containing
# high contrast and vibrant colors look best, eg. a sunset landscape.
#


from __future__ import print_function
from colorthief import MMCQ
from imagepreview import ImagePreview
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
import math
import random
import threading


def hex_to_rgb(hex):
  return tuple([int(hex[i:i + 2], 16) for i in range(1, 6, 2)])


def rgb_to_hex(rgb):
  return '#' + ''.join(['0{0:x}'.format(v) if v < 16
    else '{0:x}'.format(v) for v in rgb])


def draw_dot(x, y, r, color, img):
  draw = ImageDraw.Draw(img)
  draw.ellipse((x - r, y - r, x + r, y + r), color)


def clamp(x, a, b):
  if x < a:
    return a
  elif x > b:
    return b
  else:
    return x


def safe_get_pixel(x, y, img):
  x = clamp(x, 0, img.width - 1)
  y = clamp(y, 0, img.height - 1)
  return img.getpixel((x, y))


def draw_section(ox, oy, o, k):
  # Sample the region from the original image
  num_samples = 1000
  color_samples = []
  for _ in xrange(num_samples):
    x = random.randint(0, k.width * 2) - (k.width / 2)
    y = random.randint(0, k.height * 2) - (k.height / 2)
    color = safe_get_pixel(ox + x, oy + y, o)
    color_samples.append(color)

  # Cluster similar colors using MMCQ (modified median cut quantization)
  cmap = MMCQ.quantize(color_samples, 12)
  palette = cmap.palette
  print('palette={}'.format(palette))

  # Fill the section to create the background
  draw = ImageDraw.Draw(k)
  draw.rectangle([0, 0, k.width, k.height], fill=palette[0])

  # Draw dots to create image detail
  dot_radius_factor = 34
  dot_radius = k.width / dot_radius_factor
  num_dots = 2000
  for _ in xrange(num_dots):
    x = random.randint(0, k.width - 1)
    y = random.randint(0, k.height - 1)

    # The further we are from the center of the current region,
    # the further we sample outside the current region
    dx = (x - (k.width / 2)) / 2
    dy = (y - (k.height / 2)) / 2
    color = safe_get_pixel(ox + x + dx, oy + y + dy, o)
    color = nearish_color(color, palette)
    draw_dot(x, y, dot_radius, color, k)


def adjust(img, color=1.0, contrast=1.0, brightness=1.0):
  colorer = ImageEnhance.Color(img)
  img = colorer.enhance(color)

  contraster = ImageEnhance.Contrast(img)
  img = contraster.enhance(contrast)

  brightener = ImageEnhance.Brightness(img)
  img = brightener.enhance(brightness)

  return img


def get_material_palette():
  palette = []
  with open('material_color_palette.txt') as f:
    lines = f.readlines()
    for line in lines:
      line = line.strip()
      if line.startswith('#'):
        palette.append(hex_to_rgb(line))
  return palette


def diff_rgb(c0, c1):
  return math.sqrt((c1[0] - c0[0])**2 + (c1[1] - c0[1])**2 + (c1[2] - c0[2])**2)


def nearish_color(c, palette):
  #return min(palette, key=lambda cp: diff_rgb(c, cp))
  palette.sort(key=lambda cp: diff_rgb(c, cp))
  index = 0 if random.random() < .75 else 1
  return palette[index]


def build_mask(w, h):
  # Creates the parallelogram alpha mask.
  # (w, h) is the size of the bounding box
  mask = Image.new('RGBA', (w, h))

  draw = ImageDraw.Draw(mask)
  draw.rectangle([(0, 0), (w - 1, h - 1)], fill=(0, 0, 0, 0))

  points = [(w / 3, 0), (w, h * 2 / 3), (w * 2 / 3, h), (0, h / 3)]
  draw.polygon(points, fill=(255, 255, 255, 255))

  return mask


def gen_sections(x, y, sw, sh, w, h):
  # Computes a single row of parallelograms going from lower left
  # to upper right, which should overflow off the edges to fully
  # cover the image.
  #
  # (x, y) is the top-left point to start from
  # (sw, sh) is the size of the section
  # (w, h) is the size of the overall image to cover
  #
  # Returns the list of top-left points for each parallelogram box
  sections = []
  while (x < w) and (y + sh >= 0):
    if (x + sw >= 0) and (y < h):
      sections.append((x, y))

    x += sw / 3
    y -= sh / 3

  return sections


def show_palette(palette):
  w_color = 100
  h_color = 40
  palette_image = Image.new('RGB', (w_color, h_color * len(palette)))
  for i in xrange(len(palette)):
    draw = ImageDraw.Draw(palette_image)
    top_left = (0, i * h_color)
    bottom_right = (w_color - 1, ((i + 1) * h_color) - 1)
    draw.rectangle([top_left, bottom_right], fill=palette[i])
  palette_image.show()


def render(filepath, o, preview):
  w_section = o.width / 8
  h_section = w_section * 2 / 3

  print(w_section, h_section)

  r = Image.new(o.mode, o.size)
  mask = build_mask(w_section, h_section)

  x_init = int(-w_section * (1 + random.random()))
  y_init = int(-h_section * (1 + random.random()))
  sections = gen_sections(x_init, y_init, w_section, h_section, o.width, o.height)
  row = 0

  while y_init < 0 or len(sections) > 0:
    print('row={} sections={}'.format(row, sections))

    for (x, y) in sections:
      # Draw the current section, then paste it on the output with the shape mask.
      k = Image.new(o.mode, (w_section, h_section))
      draw_section(x, y, o, k)
      r.paste(k, box=(x, y), mask=mask)

      preview.receive(r)

    y_init += (h_section * 4 / 3) - 1
    sections = gen_sections(x_init, y_init, w_section, h_section, o.width, o.height)
    row += 1

  r.save('output/out.jpg')
  r.show()

  preview.receive(ImagePreview.CLOSE_COMMAND)


def main():
  filepath = 'input/treasure_island.JPG'
  o = Image.open(filepath).convert('RGB')
  print(o.mode, o.size, o.format, filepath)

  w = 4000
  h = int(o.height * w / float(o.width))
  o = o.resize((w, h))
  o = adjust(o, color=1.0, contrast=1.0, brightness=1.0)

  wp = 800
  hp = int(o.height * wp / float(o.width))
  preview = ImagePreview((wp, hp), o)

  t = threading.Thread(target=render, args=(filepath, o, preview))
  t.daemon = True
  t.start()

  # Open the preview window and block the main thread
  preview.start()


if __name__ == '__main__':
  main()
