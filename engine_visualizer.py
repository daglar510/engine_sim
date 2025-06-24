import matplotlib.pyplot as plt
import numpy as np

class EngineVisualizer:
    """
    Generates a 2D visual representation of an engine's geometry and state.
    Handles Inline, V, and Boxer engine configurations.
    """
    def __init__(self, bore_mm, stroke_mm, con_rod_mm, num_cylinders, config, v_angle_deg=90):
        """
        Initializes the visualizer with engine geometric parameters.

        Args:
            bore_mm (float): Cylinder bore in millimeters.
            stroke_mm (float): Piston stroke in millimeters.
            con_rod_mm (float): Connecting rod length in millimeters.
            num_cylinders (int): Number of cylinders.
            config (str): 'Inline', 'V', or 'Boxer'.
            v_angle_deg (float): The angle between cylinder banks for V-engines.
        """
        self.bore = bore_mm
        self.stroke = stroke_mm
        self.crank_radius = stroke_mm / 2.0
        self.con_rod_length = con_rod_mm
        self.num_cylinders = num_cylinders
        self.config = config
        self.v_angle_rad = np.deg2rad(v_angle_deg if self.config == 'V' else 180) # Boxer is 180-deg V

    def _get_piston_position(self, crank_angle_rad):
        """
        Calculates piston height based on the crank angle using slider-crank linkage kinematics.
        y = r*cos(theta) + sqrt(l^2 - (r*sin(theta))^2)
        """
        r = self.crank_radius
        l = self.con_rod_length
        term1 = r * np.cos(crank_angle_rad)
        term2 = np.sqrt(l**2 - (r * np.sin(crank_angle_rad))**2)
        return term1 + term2

    def draw_engine(self, crank_angle_deg):
        """
        Draws the complete engine schematic for a given crank angle.

        Args:
            crank_angle_deg (float): The current rotation of the crankshaft in degrees.

        Returns:
            matplotlib.figure.Figure: The figure object containing the plot.
        """
        crank_angle_rad = np.deg2rad(crank_angle_deg)
        fig, ax = plt.subplots(figsize=(8, 6))
        
        # --- Common drawing parameters ---
        piston_height = self.bore * 0.5 # Proportional to bore
        cylinder_spacing = self.bore * 1.2
        crank_pin_x = self.crank_radius * np.sin(crank_angle_rad)
        crank_pin_y = -self.crank_radius * np.cos(crank_angle_rad)
        
        ax.plot(crank_pin_x, crank_pin_y, 'ro', markersize=10) # Main crank pin
        ax.plot([0, crank_pin_x], [0, crank_pin_y], 'r-') # Crank web

        if self.config == 'Inline':
            for i in range(self.num_cylinders):
                x_offset = (i - (self.num_cylinders - 1) / 2) * cylinder_spacing
                self._draw_cylinder(ax, crank_angle_rad, x_offset)
        
        elif self.config in ['V', 'Boxer']:
            num_cylinders_per_bank = self.num_cylinders // 2
            for i in range(num_cylinders_per_bank):
                # Firing order offset for smoother visuals (e.g., 360/num_banks)
                # This is a simplification; real V-engine firing orders are complex.
                angle_offset = np.deg2rad(360 / num_cylinders_per_bank * i)
                bank_offset = (i - (num_cylinders_per_bank-1)/2)*cylinder_spacing
                
                # Left Bank
                self._draw_cylinder(ax, crank_angle_rad + angle_offset, x_offset=bank_offset, bank_angle=self.v_angle_rad / 2)
                # Right Bank
                self._draw_cylinder(ax, crank_angle_rad + angle_offset, x_offset=bank_offset, bank_angle=-self.v_angle_rad / 2)

        ax.set_aspect('equal', adjustable='box')
        ax.set_xlim(-self.bore * self.num_cylinders/1.5, self.bore * self.num_cylinders/1.5)
        ax.set_ylim(-self.stroke*1.5, self.stroke + self.con_rod_length + piston_height)
        ax.axis('off')
        
        return fig

    def _draw_cylinder(self, ax, crank_angle_rad, x_offset, bank_angle=0):
        """Helper function to draw a single cylinder, piston, and rod assembly."""
        # --- Kinematics ---
        piston_y = self._get_piston_position(crank_angle_rad)
        crank_pin_x = self.crank_radius * np.sin(crank_angle_rad)
        crank_pin_y = -self.crank_radius * np.cos(crank_angle_rad)
        
        # --- Components relative to cylinder center ---
        # Cylinder Block
        cyl_half_width = self.bore / 2
        cyl_height = self.stroke + self.con_rod_length * 0.2
        cyl_bottom = self.con_rod_length * 0.8
        
        # Piston
        piston_top = cyl_bottom + piston_y
        piston_bottom = piston_top - (self.stroke * 0.4)
        
        # Wrist Pin (at piston center)
        wrist_pin_y = piston_bottom + (piston_top - piston_bottom) / 2
        
        # Apply rotation for V-engine banks
        rot_matrix = np.array([
            [np.cos(bank_angle), -np.sin(bank_angle)],
            [np.sin(bank_angle), np.cos(bank_angle)]
        ])

        def rotate(points):
            return (rot_matrix @ points.T).T + np.array([x_offset, 0])

        # --- Draw Geometry ---
        # Cylinder
        cyl_points = np.array([
            [-cyl_half_width, cyl_bottom], [cyl_half_width, cyl_bottom],
            [cyl_half_width, cyl_height], [-cyl_half_width, cyl_height],
        ])
        ax.plot(*zip(*rotate(cyl_points[:2])), 'k-')
        ax.plot(*zip(*rotate(cyl_points[1:3])), 'k-', lw=1)
        ax.plot(*zip(*rotate(cyl_points[2:])), 'k-')
        ax.plot(*zip(*rotate(np.array([cyl_points[3],cyl_points[0]]))), 'k-', lw=1)

        # Piston
        piston_points = np.array([
            [-cyl_half_width, piston_bottom], [cyl_half_width, piston_bottom],
            [cyl_half_width, piston_top], [-cyl_half_width, piston_top],
            [-cyl_half_width, piston_bottom]
        ])
        ax.fill(*zip(*rotate(piston_points)), color='gray')

        # Connecting Rod
        wrist_pin_pos = rotate(np.array([[0, wrist_pin_y]]))[0]
        ax.plot([wrist_pin_pos[0], crank_pin_x], [wrist_pin_pos[1], crank_pin_y], 'b-', lw=4) 