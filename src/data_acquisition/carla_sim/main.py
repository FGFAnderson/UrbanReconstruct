import os
import random
import threading
import time
from collections import defaultdict
from datetime import datetime

import carla

# 360° rig: 4 cameras at 90° yaw intervals, matching Mapillary's multi-lens layout.
# Each camera covers ~90° FOV; together they tile the full horizontal plane.
CAMERA_DIRECTIONS = [
    ("front", 0.0),
    ("right", 90.0),
    ("back", 180.0),
    ("left", 270.0),
]


def make_camera_bp(world, image_w, image_h, fov):
    bp = world.get_blueprint_library().find("sensor.camera.rgb")
    bp.set_attribute("image_size_x", str(image_w))
    bp.set_attribute("image_size_y", str(image_h))
    bp.set_attribute("fov", str(fov))
    bp.set_attribute("sensor_tick", "2.0")
    bp.set_attribute("motion_blur_intensity", "0.0")
    bp.set_attribute("lens_flare_intensity", "0.0")
    bp.set_attribute("chromatic_aberration_intensity", "0.0")
    return bp


def main():
    out_dir = f"out/{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(out_dir, exist_ok=True)

    client = carla.Client("localhost", 2000)
    client.set_timeout(10.0)
    client.load_world("Town10HD_Opt")
    world = client.get_world()
    vehicle_blueprints = world.get_blueprint_library().filter("*vehicle*")
    spawn_points = world.get_map().get_spawn_points()
    random.shuffle(spawn_points)

    npc_vehicles = []
    used_indices = set()

    for i, sp in enumerate(spawn_points[:50]):
        actor = world.try_spawn_actor(random.choice(vehicle_blueprints), sp)
        if actor is not None:
            npc_vehicles.append(actor)
            used_indices.add(i)

    ego_vehicle = None
    for i, sp in enumerate(spawn_points):
        if i not in used_indices:
            ego_vehicle = world.try_spawn_actor(random.choice(vehicle_blueprints), sp)
            if ego_vehicle is not None:
                break

    traffic_manager = client.get_trafficmanager()
    for v in npc_vehicles:
        v.set_autopilot(True, traffic_manager.get_port())
    ego_vehicle.set_autopilot(True, traffic_manager.get_port())

    # 90° FOV per lens — four lenses tile 360° with slight overlap
    image_w, image_h, fov = 3000, 3000, 90

    mount = carla.Location(x=0.0, z=2.4)

    cameras = []
    for label, yaw in CAMERA_DIRECTIONS:
        bp = make_camera_bp(world, image_w, image_h, fov)
        transform = carla.Transform(mount, carla.Rotation(pitch=0.0, yaw=yaw, roll=0.0))
        cam = world.spawn_actor(bp, transform, attach_to=ego_vehicle)
        assert isinstance(cam, carla.Sensor), f"Failed to spawn {label} camera"
        cameras.append((label, cam))
        world.wait_for_tick()  # let the server register each sensor before spawning the next

    target_count = random.randint(150, 300)
    print(f"Target capture count: {target_count} (each = 4 images covering 360°)")

    # Callbacks fire on a CARLA background thread — protect shared state with a lock.
    frame_buffer: dict[int, dict[str, carla.Image]] = defaultdict(dict)
    capture_count = 0
    num_directions = len(CAMERA_DIRECTIONS)
    lock = threading.Lock()

    def on_image(label, image):
        nonlocal capture_count
        with lock:
            frame_buffer[image.frame][label] = image
            if len(frame_buffer[image.frame]) < num_directions:
                return
            frame_imgs = frame_buffer.pop(image.frame)

        frame_dir = os.path.join(out_dir, "%06d" % image.frame)
        os.makedirs(frame_dir, exist_ok=True)
        for direction, img in frame_imgs.items():
            img.save_to_disk(os.path.join(frame_dir, f"{direction}.png"))

        with lock:
            capture_count += 1
            count_snapshot = capture_count
        print(f"Captured 360° set {count_snapshot}/{target_count} (frame {image.frame})")

    for label, cam in cameras:
        cam.listen(lambda img, lbl=label: on_image(lbl, img))

    try:
        while True:
            with lock:
                done = capture_count >= target_count
            if done:
                break
            time.sleep(0.1)
        print(f"Reached target of {target_count} captures. Stopping.")
    except KeyboardInterrupt:
        print("Stopping early.")
    finally:
        for _, cam in cameras:
            cam.stop()
            cam.destroy()
        ego_vehicle.destroy()
        for v in npc_vehicles:
            v.destroy()
        print("Cleaned up all actors.")


if __name__ == "__main__":
    main()
