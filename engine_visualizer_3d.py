import numpy as np
import pyvista as pv

# Scale factor for converting mm to meters for internal calculations
MM_TO_M = 0.001

class EngineVisualizer3D:
    def __init__(self, bore_mm, stroke_mm, con_rod_mm,
                 num_cyl, layout='Inline', v_angle_deg=90):
        self.R = (stroke_mm / 2.0) * MM_TO_M
        self.L = con_rod_mm * MM_TO_M
        self.bore = bore_mm * MM_TO_M
        self.stroke = stroke_mm * MM_TO_M
        self.layout = layout
        self.v_angle = np.radians(v_angle_deg if self.layout == 'V' else 180) # Boxer is 180-deg V
        self.num_cyl = num_cyl

    def _piston_z(self, crank_rad):
        """Calculates piston height from crank angle."""
        # Clamp the term inside sqrt to prevent math domain error from floating point inaccuracies
        sqrt_term = self.L**2 - (self.R * np.sin(crank_rad))**2
        if sqrt_term < 0: sqrt_term = 0
        return self.R * np.cos(crank_rad) + np.sqrt(sqrt_term)

    def _create_cylinder_assembly(self, plotter, crank_rad, y_offset, bank_angle_rad=0):
        """Builds and adds a single cylinder, piston, and rod to the scene."""
        z_piston_local = self._piston_z(crank_rad)
        
        # --- Crankshaft Components (per cylinder) ---
        crank_throw_radius = self.R * 0.8
        crank_web_thickness = self.bore * 0.2
        # Crank Pin
        crank_pin_pos = np.array([self.R * np.sin(crank_rad), y_offset, -self.R * np.cos(crank_rad)])
        crank_pin = pv.Cylinder(center=crank_pin_pos, direction=(0, 1, 0), radius=crank_throw_radius*0.6, height=crank_web_thickness*2)
        
        # Crank Webs
        main_journal_pos1 = np.array([0, y_offset - crank_web_thickness, 0])
        main_journal_pos2 = np.array([0, y_offset + crank_web_thickness, 0])
        web1 = pv.Cylinder(center=(crank_pin_pos + main_journal_pos1)/2, direction=main_journal_pos1-crank_pin_pos,
                           radius=crank_throw_radius, height=np.linalg.norm(main_journal_pos1-crank_pin_pos))
        web2 = pv.Cylinder(center=(crank_pin_pos + main_journal_pos2)/2, direction=main_journal_pos2-crank_pin_pos,
                           radius=crank_throw_radius, height=np.linalg.norm(main_journal_pos2-crank_pin_pos))

        plotter.add_mesh(crank_pin, color='#c0c0c0', metallic=1.0, roughness=0.2)
        plotter.add_mesh(web1, color='#c0c0c0', metallic=1.0, roughness=0.2)
        plotter.add_mesh(web2, color='#c0c0c0', metallic=1.0, roughness=0.2)
        
        # --- Piston and Rod (Rotated for V-engines) ---
        # Create rotation matrix for V-engine banks
        rotation_matrix = pv.transformations.axis_angle_rotation((0, 1, 0), np.degrees(bank_angle_rad))
        
        # Piston
        piston_center = np.array([0, 0, z_piston_local])
        piston = pv.Cylinder(center=piston_center, direction=(0, 0, 1), radius=self.bore/2, height=self.bore*0.3)
        
        # Connecting Rod - Recreated each frame for accurate positioning
        wrist_pin_pos_local = np.array([0, 0, z_piston_local])
        crank_pin_pos_local = np.array([self.R * np.sin(crank_rad), 0, -self.R * np.cos(crank_rad)])
        
        # Cylinder Liner
        liner_height = self.stroke + self.bore*0.3
        liner_center = [0, 0, self.L + liner_height/2 - self.R]
        liner = pv.Cylinder(center=liner_center, direction=(0, 0, 1), radius=self.bore/2 + (3 * MM_TO_M), height=liner_height)
        
        # Apply transformations: rotate first, then translate
        # Temporarily create rod to transform its points, then create the final tube
        rod_points_mesh = pv.Line(wrist_pin_pos_local, crank_pin_pos_local)
        
        for mesh in [piston, rod_points_mesh, liner]:
            mesh.transform(rotation_matrix, inplace=True)
            mesh.translate([0, y_offset, 0], inplace=True)
        
        # Create final connecting rod between transformed points
        rod = pv.Cylinder(center=(rod_points_mesh.points[0] + rod_points_mesh.points[1])/2,
                          direction=rod_points_mesh.points[1] - rod_points_mesh.points[0],
                          radius=self.bore * 0.04,
                          height=np.linalg.norm(rod_points_mesh.points[1] - rod_points_mesh.points[0]))

        piston_texture = pv.read_texture('./assets/brushed_metal.png') # Optional texture
        plotter.add_mesh(piston, texture=piston_texture, color='silver', metallic=0.8, roughness=0.4)
        plotter.add_mesh(rod, color='tan', metallic=0.6, roughness=0.5)
        plotter.add_mesh(liner, color='#4a4a4a', opacity=0.25, smooth_shading=True)

    def build_scene(self, crank_deg=0, height=600):
        """Constructs the full PyVista plotter scene."""
        plotter = pv.Plotter(window_size=[800, height], lighting='three lights')
        crank_rad_base = np.radians(crank_deg)
        
        cylinder_spacing = self.bore * 1.3
        
        # --- Central Crankshaft ---
        # Draw a single main shaft for visual continuity
        num_throws = self.num_cyl if self.layout == 'Inline' else self.num_cyl // 2
        crankshaft_length = num_throws * cylinder_spacing
        main_shaft = pv.Cylinder(center=(0, crankshaft_length/2 - cylinder_spacing/2, 0), direction=(0, 1, 0),
                                 radius=self.bore * 0.15, height=crankshaft_length)
        plotter.add_mesh(main_shaft, color='#a0a0a0', metallic=1.0, roughness=0.3)

        # --- Engine Block ---
        if self.layout == 'Inline':
            block_width = self.bore * 1.5
            block_length = self.num_cyl * cylinder_spacing
            block_height = self.L + self.stroke
            block_center = (0, block_length/2 - cylinder_spacing/2, block_height/2 - self.R)
            block = pv.Cube(center=block_center, x_length=block_width, y_length=block_length, z_length=block_height)
            
            # Cylinder Head
            head_height = self.bore * 0.5
            head_center = (block_center[0], block_center[1], block_center[2] + block_height/2 + head_height/2)
            head = pv.Cube(center=head_center, x_length=block_width*1.1, y_length=block_length, z_length=head_height)

            plotter.add_mesh(block, color='#333333', roughness=0.7, opacity=0.1)
            plotter.add_mesh(head, color='#282828', roughness=0.8)
        
        elif self.layout == 'V':
            num_cyl_per_bank = self.num_cyl // 2
            block_width = self.bore * 1.5
            block_length = num_cyl_per_bank * cylinder_spacing
            block_height = self.L + self.stroke
            
            # Create a 'proto' block and head aligned with the Z-axis that we can copy and rotate
            proto_block_center = (0, block_length/2 - cylinder_spacing/2, block_height/2 - self.R)
            proto_block = pv.Cube(center=proto_block_center, x_length=block_width, y_length=block_length, z_length=block_height)
            
            head_height = self.bore * 0.5
            proto_head_center = (proto_block_center[0], proto_block_center[1], proto_block_center[2] + block_height/2 + head_height/2)
            proto_head = pv.Cube(center=proto_head_center, x_length=block_width*1.1, y_length=block_length, z_length=head_height)
            
            # Left bank
            left_block = proto_block.copy()
            left_head = proto_head.copy()
            left_rotation = pv.transformations.axis_angle_rotation((0, 1, 0), np.degrees(-self.v_angle / 2))
            left_block.transform(left_rotation, inplace=True)
            left_head.transform(left_rotation, inplace=True)
            plotter.add_mesh(left_block, color='#333333', roughness=0.7, opacity=0.1)
            plotter.add_mesh(left_head, color='#282828', roughness=0.8)

            # Right bank
            right_block = proto_block.copy()
            right_head = proto_head.copy()
            right_rotation = pv.transformations.axis_angle_rotation((0, 1, 0), np.degrees(self.v_angle / 2))
            right_block.transform(right_rotation, inplace=True)
            right_head.transform(right_rotation, inplace=True)
            plotter.add_mesh(right_block, color='#333333', roughness=0.7, opacity=0.1)
            plotter.add_mesh(right_head, color='#282828', roughness=0.8)

        # --- Build each cylinder assembly ---
        firing_order_deg = 720 / self.num_cyl
        if self.layout == 'Inline':
            for i in range(self.num_cyl):
                y_offset = (i - (self.num_cyl - 1) / 2.0) * cylinder_spacing
                crank_rad = crank_rad_base + np.deg2rad(i * firing_order_deg)
                self._create_cylinder_assembly(plotter, crank_rad, y_offset=y_offset)
        
        elif self.layout in ['V', 'Boxer']:
            num_banks = self.num_cyl // 2
            for i in range(num_banks):
                y_offset = (i - (num_banks - 1) / 2.0) * cylinder_spacing
                # Fire left and right bank cylinders on the same crank throw
                crank_rad = crank_rad_base + np.deg2rad(i * (720 / num_banks))
                # Left Bank
                self._create_cylinder_assembly(plotter, crank_rad, y_offset=y_offset, bank_angle_rad=-self.v_angle / 2)
                # Right Bank
                self._create_cylinder_assembly(plotter, crank_rad, y_offset=y_offset, bank_angle_rad=self.v_angle / 2)

        # --- Scene Setup ---
        plotter.add_light(pv.Light(position=(1, 1, 1), light_type='scenelight', color='white', intensity=0.6))
        plotter.add_light(pv.Light(position=(-1, -1, 1), light_type='scenelight', color='white', intensity=0.6))
        plotter.add_light(pv.Light(position=(1, -1, -1), light_type='scenelight', color='white', intensity=0.3))
        
        plotter.renderer.SetAmbient(0.2, 0.2, 0.2) # Set ambient light for the whole scene

        plotter.set_background('darkslategrey')
        plotter.enable_parallel_projection()
        plotter.enable_eye_dome_lighting()
        plotter.camera_position = 'iso'
        plotter.camera.azimuth = -45
        plotter.camera.elevation = 20
        plotter.camera.zoom(1.2)
        plotter.enable_trackball_style()
        return plotter 