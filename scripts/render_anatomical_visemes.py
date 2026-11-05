import cv2
import numpy as np
from PIL import Image

# Load original pristine avatar
base = cv2.imread("frontend/public/images/zaira-avatar.png", cv2.IMREAD_UNCHANGED)
h, w = base.shape[:2]

# Center coordinates of Zaira's mouth
cx, cy = 520, 334
# Mouth corners: left=471, right=570 -> half_w = 48
lip_top = 323
lip_bottom = 353
chin_bottom = 415

def make_viseme_frame(dy, aperture_w, aperture_h, roundness=1.0):
    """
    Creates an anatomically realistic speaking frame:
    - dy: vertical jaw drop in pixels
    - aperture_w: width of the oral opening in pixels
    - aperture_h: height of the oral opening in pixels
    - roundness: shape modifier (1.0 = normal oval, 0.7 = wide slit, 1.4 = round)
    """
    frame = base.copy().astype(np.float32)
    
    # 1. Deform lower lip and chin downward by dy
    # Region of lower face: x from 440 to 600, y from 334 to 430
    rx1, rx2 = 440, 600
    ry1, ry2 = 334, 430
    patch = frame[ry1:ry2, rx1:rx2].copy()
    ph, pw = patch.shape[:2]
    
    # Cosine vertical falloff from y=334 (max shift = dy) down to chin (shift = 0)
    y_r = np.arange(ph, dtype=np.float32)
    v_weight = 0.5 * (1.0 + np.cos(np.pi * y_r / ph))
    
    # Horizontal parabolic falloff from center (cx) to corners
    x_r = np.arange(pw, dtype=np.float32)
    center_local_x = cx - rx1
    h_weight = np.clip(1.0 - ((x_r - center_local_x) / (aperture_w * 0.75)) ** 2, 0.0, 1.0)
    
    # 2D shift map
    shift_y = np.outer(v_weight, h_weight) * dy
    
    # Remap grid
    grid_x = np.tile(x_r, (ph, 1))
    grid_y = np.tile(y_r, (pw, 1)).T - shift_y
    grid_y = np.clip(grid_y, 0, ph - 1)
    
    warped_patch = cv2.remap(patch, grid_x, grid_y, cv2.INTER_LINEAR)
    
    # Feathered blend around the edges of the patch
    blend_weight = np.zeros((ph, pw), dtype=np.float32)
    for r in range(ph):
        for c in range(pw):
            if shift_y[r, c] > 0.1:
                blend_weight[r, c] = min(1.0, shift_y[r, c] / 1.5)
    blend_weight = cv2.GaussianBlur(blend_weight, (11, 11), 3.0)
    blend_weight = np.dstack([blend_weight] * 4)
    
    frame[ry1:ry2, rx1:rx2] = warped_patch * blend_weight + frame[ry1:ry2, rx1:rx2] * (1.0 - blend_weight)
    
    # 2. Render Anatomical Oral Cavity & Upper Teeth inside the opening
    # Opening bounds centered at (cx, cy + dy * 0.35)
    open_cy = int(cy + dy * 0.38)
    half_aw = aperture_w // 2
    half_ah = max(2, aperture_h // 2)
    
    ox1 = max(0, cx - half_aw)
    ox2 = min(w, cx + half_aw)
    oy1 = max(0, open_cy - half_ah)
    oy2 = min(h, open_cy + half_ah)
    
    box_w = ox2 - ox1
    box_h = oy2 - oy1
    
    if box_w > 0 and box_h > 0:
        # Create oral opening canvas
        cavity = np.zeros((box_h, box_w, 3), dtype=np.float32)
        
        # Deep dark oral background (deep velvety dark red/shadow)
        cavity[:, :] = [24.0, 18.0, 32.0] # BGR dark maroon/shadow
        
        # Upper teeth layer: sits in the upper 45% of the opening
        teeth_h = max(3, int(box_h * 0.48))
        teeth_w = int(box_w * 0.72)
        tx1 = (box_w - teeth_w) // 2
        tx2 = tx1 + teeth_w
        
        for ty in range(teeth_h):
            # Curved dental arch: slightly higher at corners, lower in center incisors
            curve = np.cos(np.pi * (np.arange(teeth_w) - teeth_w / 2) / teeth_w)
            for tx in range(teeth_w):
                # Teeth shading: ivory white with subtle vertical gradient and dental separation
                arch_y = ty - (1.0 - curve[tx]) * 1.5
                if 0 <= arch_y < teeth_h:
                    # Natural tooth brightness (brightest at bottom cutting edge)
                    brightness = 190.0 + (arch_y / teeth_h) * 35.0
                    # Subtle tooth separation lines every ~9 pixels
                    tooth_sep = 1.0 - 0.18 * (np.sin(tx * (np.pi / 4.5)) ** 8)
                    tooth_b = min(255.0, (brightness - 12.0) * tooth_sep) # slight warm ivory
                    tooth_g = min(255.0, (brightness - 4.0) * tooth_sep)
                    tooth_r = min(255.0, (brightness + 5.0) * tooth_sep)
                    cavity[ty, tx1 + tx] = [tooth_b, tooth_g, tooth_r]
                    
        # Lower teeth edge (subtle hint if opening is large enough)
        if box_h >= 10:
            lt_h = 2
            lt_w = int(box_w * 0.55)
            ltx1 = (box_w - lt_w) // 2
            for ty in range(box_h - lt_h, box_h):
                for tx in range(lt_w):
                    cavity[ty, ltx1 + tx] = [170.0, 180.0, 195.0]
                    
        # Feathered aperture mask (natural lip shape)
        mask = np.zeros((box_h, box_w), dtype=np.float32)
        cv2.ellipse(
            mask,
            (box_w // 2, box_h // 2),
            (max(1, box_w // 2 - 2), max(1, box_h // 2 - 1)),
            0, 0, 360, 1.0, -1
        )
        mask = cv2.GaussianBlur(mask, (7, 7), 2.0)
        mask_3 = np.dstack([mask] * 3)
        
        # Blend cavity into frame
        bg = frame[oy1:oy2, ox1:ox2, :3]
        frame[oy1:oy2, ox1:ox2, :3] = cavity * mask_3 + bg * (1.0 - mask_3)
        
    return np.clip(frame, 0, 255).astype(np.uint8)

# Generate 4 distinct anatomical viseme frames:
# 1. Rest (closed smile): pristine base image
cv2.imwrite("frontend/public/images/zaira-viseme-0.png", base)
print("Saved zaira-viseme-0.png (Rest closed)")

# 2. Slight open (consonants / soft sound): dy=5, aperture 52x5
f1 = make_viseme_frame(dy=5, aperture_w=52, aperture_h=5, roundness=0.8)
cv2.imwrite("frontend/public/images/zaira-viseme-1.png", f1)
print("Saved zaira-viseme-1.png (Slight open)")

# 3. Medium open (normal speech / talking vowels): dy=10, aperture 64x10
f2 = make_viseme_frame(dy=10, aperture_w=64, aperture_h=10, roundness=1.0)
cv2.imwrite("frontend/public/images/zaira-viseme-2.png", f2)
print("Saved zaira-viseme-2.png (Medium open)")

# 4. Wide open (emphasis / open vowels 'aa', 'ah'): dy=16, aperture 72x16
f3 = make_viseme_frame(dy=16, aperture_w=72, aperture_h=16, roundness=1.1)
cv2.imwrite("frontend/public/images/zaira-viseme-3.png", f3)
print("Saved zaira-viseme-3.png (Wide open)")

# 5. Round vowel ('oo', 'oh', 'w'): dy=9, aperture 46x12
f4 = make_viseme_frame(dy=9, aperture_w=46, aperture_h=12, roundness=1.4)
cv2.imwrite("frontend/public/images/zaira-viseme-4.png", f4)
print("Saved zaira-viseme-4.png (Round vowel)")
