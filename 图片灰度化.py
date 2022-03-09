from PIL import Image

input("it will open the picture.png are you sure about it?")

f = open("out_put.txt", 'w+')  
im = Image.open("picture.png")
img = im.convert('L')
for i in range(10):
	for j in range(10):
		r = img.getpixel((i, j))
		print(r,file=f)
img.show()
