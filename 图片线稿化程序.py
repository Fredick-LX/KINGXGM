import os
try:
    from PIL import Image
expect:
    os.system("pip install pillow")
try:
    import numpy as np
expect:
    os.system("pip install numpy")
import time
print("请将图片置于本文件的同一目录下")
name = input("文件名是:\n")
def main():
    vec_el = np.pi/float(input("请输入俯视角参数（建议值:2.2）:"))
    vec_az = np.pi/float(input("请输入方位角参数（建议值:4.0）:"))
    level = float(input("请输入深度参数（建议值:120）:"))
    depth = 10.
    im1 = Image.open(name).convert('L')
    a = np.asarray(im1).astype('float')
    grad = np.gradient(a)
    grad_x,grad_y=grad
    grad_x = grad_x*depth/level
    grad_y = grad_y*depth/level
    dx = np.cos(vec_el)*np.cos(vec_az)
    dy = np.cos(vec_el)*np.cos(vec_az)
    dz = np.sin(vec_el)
    A = np.sqrt(grad_x**2+grad_y**2+1.)
    uni_x = grad_x/A
    uni_y = grad_y/A
    uni_z = 1./A
    a2 = 255*(dx*uni_x+dy*uni_y+dz*uni_z)
    a2 = a2.clip(0,255)
    im2 = Image.fromarray(a2.astype('uint8'))
    im2.save("OUT"+str(level)+".jpg")
    print("已完成创建,深度为"+str(level))
    time.sleep(0.5)
while True:
    try:
        main()
        if input("是否退出?是请输入y,否请输入其他字符\n") == "y":
            break
    except:
        print("发现错误，请检查\n1.俯视角参数,请输入方位角参数,深度参数是否输入正确\n2.请检查图片名是否为IN.jpg并在同一目录下")
        if input("是否退出?是请输入y,否请输入其他字符\n") == "y":
            break
