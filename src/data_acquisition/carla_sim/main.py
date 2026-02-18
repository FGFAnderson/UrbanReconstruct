import os
import random
import time

import carla


def main():
    os.makedirs("out", exist_ok=True)
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

    camera_bp = world.get_blueprint_library().find("sensor.camera.rgb")
    camera_bp.set_attribute("image_size_x", "4000")
    camera_bp.set_attribute("image_size_y", "3000")
    camera_bp.set_attribute("fov", "110")
    camera_bp.set_attribute("sensor_tick", "2.0")
    camera_init_trans = carla.Transform(
        carla.Location(x=1.5, z=2.4),
        carla.Rotation(pitch=0.0, yaw=0.0, roll=0.0),
    )
    camera = world.spawn_actor(camera_bp, camera_init_trans, attach_to=ego_vehicle)
    assert isinstance(camera, carla.Sensor)

    target_count = random.randint(150, 300)
    image_count = 0
    print(f"Target image count: {target_count}")

    def on_image(image):
        nonlocal image_count
        image.save_to_disk("out/%06d.png" % image.frame)
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
