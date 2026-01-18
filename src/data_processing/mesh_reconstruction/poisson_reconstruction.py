import open3d as o3d

def poisson_reconstruction(input_file_path: str, output_file_path) -> None:
    # Load the point cloud
    point_cloud = o3d.io.read_point_cloud(input_file_path)
    print(f"Loaded point cloud with {len(point_cloud.points)} points")

    point_cloud.estimate_normals(
        search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30)
    )
    
    # Poisson surface reconstruction
    mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
        point_cloud, depth=9
    )
    print(f"Mesh created with {len(mesh.vertices)} vertices and {len(mesh.triangles)} triangles")
    
    # Save the mesh
    o3d.io.write_triangle_mesh(f"{output_file_path}/reconstructed_mesh.ply", mesh)
    print("Mesh saved to reconstructed_mesh.ply")