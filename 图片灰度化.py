from PIL import Image

f = open("1.txt", 'w+')  
im = Image.open("C:\\Users\\PC181221\\Desktop\\图片处理\\1.png")
img = im.convert('L')
for i in range(10):
	for j in range(10):
		r = img.getpixel((i, j))
		print(r,file=f)
img.show()
