import os
import cv2
import py360convert
from PIL import Image

def is_360_image(image_path: str) -> bool:
    """Finds if an image is 360 based on its aspect ratio

    Args:
        image_path (str): Path to image

    Returns:
        bool: If the image is 360 return true, if not false
    """
    img = Image.open(image_path)
    width, height = img.size
    
    aspect_ratio = width / height
    if 1.9 < aspect_ratio < 2.1:
        return True
    
    return False

def prepare_images_for_colmap(input_dir: str, output_dir: str) -> None:
    """Convert 360 images to rectilinear perspective

    Args:
        input_dir (str): directory of images
        output_dir (str): directory to output images
    """
    os.makedirs(output_dir, exist_ok=True)
    
    for filename in os.listdir(input_dir):
        if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            continue
        
        input_path = os.path.join(input_dir, filename)
        
        if is_360_image(input_path):
            print(f"Converting 360° image: {filename}")
            img = cv2.imread(input_path)
            
            # Extract front, right, back, left images
            for angle, direction in [(0, 'front'), (90, 'right'), (180, 'back'), (270, 'left')]:
                view = py360convert.e2p(img, fov_deg=90, u_deg=angle, v_deg=0, 
                                       out_hw=(1024, 1024), mode='bilinear')
                output_name = f"{os.path.splitext(filename)[0]}_{direction}.jpg"
                cv2.imwrite(os.path.join(output_dir, output_name), view)
        else:
            print(f"Copying normal image: {filename}")
            img = cv2.imread(input_path)
            cv2.imwrite(os.path.join(output_dir, filename), img)

def main():
    prepare_images_for_colmap("./bbox_images", "./images")


if __name__ == "__main__":
    main()
