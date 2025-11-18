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

def main():
    print(is_360_image("./9V1enNuaCEx-O_byo0RVIg_0001_1345970072439378.jpg"))


if __name__ == "__main__":
    main()
