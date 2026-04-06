import json
import math
import os
import random
import time
from datetime import datetime

import carla
import numpy as np


def get_intrinsics(image_width: int, image_height: int, fov_degrees: float) -> list:
    """Compute 3x3 camera intrinsic matrix from image dimensions and horizontal FOV."""
    fx = image_width / (2 * math.tan(math.radians(fov_degrees) / 2))
    fy = fx
    cx = image_width / 2.0
    cy = image_height / 2.0
    return [[fx, 0.0, cx], [0.0, fy, cy], [0.0, 0.0, 1.0]]


def get_mapillary_pose(camera: carla.Actor, vehicle: carla.Actor) -> list:
    """
    Build a cam2world pose as Mapillary would: GPS position + compass heading only.
    No pitch, no roll, no perfect camera extraction.

    Position: camera's world location (simulates GPS on the mounted device).
    Rotation: vehicle yaw only (compass heading), assuming level camera.

    World frame is right-handed (CARLA world with Y-axis flipped).
    OpenCV camera convention: X=Right, Y=Down, Z=Forward.
    """
    loc = camera.get_transform().location
    yaw = math.radians(vehicle.get_transform().rotation.yaw)

    # Position in RH world (flip CARLA's LH Y axis)
    t = np.array([loc.x, -loc.y, loc.z])

    # Yaw-only rotation around world Z (up), RH convention
    cos_y, sin_y = math.cos(yaw), math.sin(yaw)
    R_world = np.array(
        [
            [cos_y, -sin_y, 0],
            [sin_y, cos_y, 0],
            [0, 0, 1],
        ]
    )

    # Camera looks along its local X in CARLA → map to OpenCV axes
    # OpenCV X (right)   = world col 1 (right)
    # OpenCV Y (down)    = world col 2 negated (−up)
    # OpenCV Z (forward) = world col 0 (forward)
    R_ocv = np.stack([R_world[:, 1], -R_world[:, 2], R_world[:, 0]], axis=1)

    pose = np.eye(4)
    pose[:3, :3] = R_ocv
    pose[:3, 3] = t
    return pose.tolist()


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

    image_w, image_h, fov = 4000, 3000, 110
    camera_bp = world.get_blueprint_library().find("sensor.camera.rgb")
    camera_bp.set_attribute("image_size_x", str(image_w))
    camera_bp.set_attribute("image_size_y", str(image_h))
    camera_bp.set_attribute("fov", str(fov))
    camera_bp.set_attribute("sensor_tick", "2.0")
    camera_bp.set_attribute("motion_blur_intensity", "0.0")
    camera_bp.set_attribute("lens_flare_intensity", "0.0")
    camera_bp.set_attribute("chromatic_aberration_intensity", "0.0")

    camera_init_trans = carla.Transform(
        carla.Location(x=1.5, z=2.4),
        carla.Rotation(pitch=0.0, yaw=0.0, roll=0.0),
    )
    camera = world.spawn_actor(camera_bp, camera_init_trans, attach_to=ego_vehicle)
    assert isinstance(camera, carla.Sensor)

    intrinsics = get_intrinsics(image_w, image_h, fov)

    target_count = random.randint(150, 300)
    image_count = 0
    print(f"Target image count: {target_count}")

    def on_image(image):
        nonlocal image_count
        stem = "%06d" % image.frame
        image.save_to_disk(f"{out_dir}/{stem}.png")

        pose = get_mapillary_pose(camera, ego_vehicle)
        meta = {
            "frame": image.frame,
            "intrinsics": intrinsics,
            "camera_pose": pose,
            "is_metric_scale": True,
        }
        with open(f"{out_dir}/{stem}.json", "w") as f:
            json.dump(meta, f)

        image_count += 1
        print(f"Captured image {image_count}/{target_count}")

    camera.listen(on_image)
    try:
        while image_count < target_count:
            time.sleep(0.1)
        print(f"Reached target of {target_count} images. Stopping.")
    except KeyboardInterrupt:
        print("Stopping early.")
    finally:
        camera.stop()
        camera.destroy()
        ego_vehicle.destroy()
        for v in npc_vehicles:
            v.destroy()
        print("Cleaned up all actors.")


if __name__ == "__main__":
    main()
