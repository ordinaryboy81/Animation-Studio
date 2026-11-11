"""Bir resmin üstüne numaralı ızgara çizer (kukla pin koordinatlarını okumak için).
Kullanım: python tools/grid.py karakter.png izgara.png [aralik=50]"""
import sys
from PIL import Image, ImageDraw

kaynak, hedef = sys.argv[1], sys.argv[2]
ara = int(sys.argv[3]) if len(sys.argv) > 3 else 50
im = Image.open(kaynak).convert("RGBA")
zemin = Image.new("RGBA", im.size, (225, 60, 70, 255))   # saydam yerler kırmızı görünsün
zemin.alpha_composite(im)
d = ImageDraw.Draw(zemin)
for x in range(0, im.width, ara):
    d.line([(x, 0), (x, im.height)], fill=(255, 255, 255, 160 if x % (ara * 2) == 0 else 70))
    if x % (ara * 2) == 0:
        d.text((x + 3, 3), str(x), fill="white")
for y in range(0, im.height, ara):
    d.line([(0, y), (im.width, y)], fill=(255, 255, 255, 160 if y % (ara * 2) == 0 else 70))
    if y % (ara * 2) == 0:
        d.text((3, y + 3), str(y), fill="white")
zemin.convert("RGB").save(hedef)
print("Izgara kaydedildi:", hedef, f"({im.width}x{im.height})")
