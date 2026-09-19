import js
import math
import random
from pyodide.ffi import create_proxy

# --- KONSTANTA & TEMA ---
CANVAS_W = 360
CANVAS_H = 520
GRAVITY = 0.4
BOUNCINESS = -0.6
SPAWN_ZONE_H = 70
BUCKET_H = 45

THEME = {
    "pink": "#ff007f",
    "cyan": "#00f5d4",
    "yellow": "#ffbe0b",
    "purple": "#7b2cbf",
    "blue": "#00b4d8",
    "bg": "#050510",
}
COLORS = [THEME["pink"], THEME["cyan"], THEME["yellow"], THEME["purple"], THEME["blue"]]

ZONES = [
    {"score": 50, "label": "50", "color": THEME["blue"], "bonus": 0},
    {"score": 100, "label": "100", "color": THEME["cyan"], "bonus": 0},
    {"score": 500, "label": "500\n+1 \u26A1", "color": THEME["yellow"], "bonus": 1},
    {"score": 100, "label": "100", "color": THEME["cyan"], "bonus": 0},
    {"score": 50, "label": "50", "color": THEME["blue"], "bonus": 0},
]
ZONE_W = CANVAS_W / len(ZONES)

# --- STATE GAME ---
canvas = js.document.getElementById("gameCanvas")
ctx = canvas.getContext("2d")

state = {
    "status": "START", 
    "score": 0,
    "energy": 30,
    "combo": 0,
    "max_combo": 0,
    "combo_timer": 0,
    "total_bounces": 0,
    "missions_cleared": 0,
    "burst_mode": False,
    "shake_timer": 0,
    "layout_index": 0,
}

mission = {"type": "", "target": 0, "progress": 0, "completed": False, "desc": ""}

balls = []
pegs = []
particles = []
floating_texts = []

# --- REFERENSI DOM ---
dom = {
    "score": js.document.getElementById("score"),
    "combo": js.document.getElementById("combo"),
    "energy": js.document.getElementById("ball-count"),
    "mission_text": js.document.getElementById("mission-text"),
    "mission_fill": js.document.getElementById("mission-fill"),
    "overlay": js.document.getElementById("game-overlay"),
    "overlay_title": js.document.getElementById("overlay-title"),
    "overlay_desc": js.document.getElementById("overlay-desc"),
    "menu_mode": js.document.getElementById("menu-mode-select"),
    "go_content": js.document.getElementById("game-over-content"),
    "go_rank": js.document.getElementById("go-rank"),
    "go_score": js.document.getElementById("go-score"),
    "go_combo": js.document.getElementById("go-combo"),
    "go_bounce": js.document.getElementById("go-bounce"),
    "go_mission": js.document.getElementById("go-mission"),
    "btn_start": js.document.getElementById("btn-start"),
    "btn_mode": js.document.getElementById("btn-mode"),
    "btn_menu": js.document.getElementById("btn-menu")
}

def ensure_resume_button():
    resume_btn = js.document.getElementById("btn-resume")
    if not resume_btn:
        resume_btn = js.document.createElement("button")
        resume_btn.id = "btn-resume"
        resume_btn.innerText = "LANJUTKAN PERMAINAN"
        resume_btn.style.width = "100%"
        resume_btn.style.padding = "12px"
        resume_btn.style.marginTop = "10px"
        resume_btn.style.background = THEME["cyan"]
        resume_btn.style.color = "#050510"
        resume_btn.style.border = "none"
        resume_btn.style.borderRadius = "8px"
        resume_btn.style.fontWeight = "bold"
        resume_btn.style.cursor = "pointer"
        resume_btn.style.display = "none"
        
        dom["btn_start"].parentNode.insertBefore(resume_btn, dom["btn_start"])
        resume_btn.addEventListener("click", create_proxy(resume_game))
    return js.document.getElementById("btn-resume")

# --- SISTEM MISI & RANKING ---
def generate_mission():
    types = ["score", "bounce", "combo", "zone500"]
    m_type = random.choice(types)
    if m_type == "score": return {"type": m_type, "target": 3500, "progress": 0, "completed": False, "desc": "Kumpulkan 3500 Poin"}
    elif m_type == "bounce": return {"type": m_type, "target": 100, "progress": 0, "completed": False, "desc": "Pantulkan Bola 100 Kali"}
    elif m_type == "combo": return {"type": m_type, "target": 25, "progress": 0, "completed": False, "desc": "Capai Combo x25"}
    elif m_type == "zone500": return {"type": m_type, "target": 5, "progress": 0, "completed": False, "desc": "Masuk Zona Kuning 5x"}

def reset_mission_and_pegs(*args):
    global mission
    if state["status"] != "PLAYING": return
    
    mission = generate_mission()
    dom["mission_text"].innerText = mission["desc"]
    dom["mission_fill"].style.width = "0%"
    dom["mission_fill"].style.background = THEME["blue"]
    dom["mission_fill"].style.boxShadow = f"0 0 8px {THEME['blue']}"
    
    diff = getattr(js, "selectedDifficulty", "easy")
    init_pegs(diff)
    
    trigger_shake(12)
    spawn_floating_text(CANVAS_W/2, CANVAS_H/2, "POLA RINTANGAN BERGANTI!", THEME["cyan"], 1.5)
    spawn_floating_text(CANVAS_W/2, CANVAS_H/2 + 25, "Misi Baru Dimulai!", THEME["pink"], 1.2)

def update_mission(m_type, amount=1, set_val=False):
    if mission["completed"]: return
    if mission["type"] == m_type:
        mission["progress"] = max(mission["progress"], amount) if set_val else mission["progress"] + amount
        
        pct = min(100, (mission["progress"] / mission["target"]) * 100)
        dom["mission_fill"].style.width = f"{pct}%"
        
        if mission["progress"] >= mission["target"]:
            mission["completed"] = True
            state["missions_cleared"] += 1
            
            dom["mission_fill"].style.background = THEME["yellow"]
            dom["mission_fill"].style.boxShadow = f"0 0 10px {THEME['yellow']}"
            dom["mission_text"].innerText = "YAY! MISI SELESAI (+1500 Poin)"
            
            spawn_floating_text(CANVAS_W/2, CANVAS_H/2, "MISI SELESAI!", THEME["yellow"], 1.8)
            trigger_shake(15)
            add_score(1500)
            
            js.setTimeout(create_proxy(reset_mission_and_pegs), 2000)

def get_rank():
    s = state["score"]
    if s >= 10000: return "SSS", THEME["yellow"]
    if s >= 7000: return "SS", THEME["cyan"]
    if s >= 5000: return "S", THEME["pink"]
    if s >= 3000: return "A", THEME["purple"]
    if s >= 1500: return "B", THEME["blue"]
    return "C", "#aaaaaa"

# --- EFEK VISUAL ---
def spawn_particles(x, y, color, amount=10, speed=3.0):
    for _ in range(amount):
        particles.append({
            "x": x, "y": y,
            "vx": random.uniform(-speed, speed),
            "vy": random.uniform(-speed, speed),
            "life": 1.0, "decay": random.uniform(0.02, 0.05),
            "color": color, "size": random.uniform(2, 5)
        })

def spawn_floating_text(x, y, text, color, scale=1.0):
    floating_texts.append({
        "x": x, "y": y, "text": text, "color": color,
        "life": 1.0, "vy": -1.5, "scale": scale
    })

def trigger_shake(intensity=10):
    state["shake_timer"] = intensity

def apply_shake():
    if state["shake_timer"] > 0:
        if state["shake_timer"] > 10: canvas.classList.add("shake-hard")
        else:
            canvas.classList.add("shake")
            canvas.classList.remove("shake-hard")
        state["shake_timer"] -= 1
    else:
        canvas.classList.remove("shake")
        canvas.classList.remove("shake-hard")

# --- LOGIKA GAME ---
def add_score(val):
    state["score"] += val
    dom["score"].innerText = str(state["score"])
    
    dom["score"].style.transform = "scale(1.2)"
    js.setTimeout(create_proxy(lambda *args: setattr(dom["score"].style, "transform", "scale(1)")), 100)
    
    update_mission("score", state["score"], set_val=True)

def handle_combo():
    state["combo"] += 1
    state["combo_timer"] = 120 
    if state["combo"] > state["max_combo"]: state["max_combo"] = state["combo"]
    
    dom["combo"].innerText = str(state["combo"])
    update_mission("combo", state["combo"], set_val=True)
    
    if state["combo"] == 10: spawn_floating_text(CANVAS_W/2, 120, "MANTAP!", THEME["cyan"], 1.3)
    elif state["combo"] == 20: spawn_floating_text(CANVAS_W/2, 120, "SUPER COMBO!", THEME["pink"], 1.6)
    elif state["combo"] == 35: 
        spawn_floating_text(CANVAS_W/2, 120, "GILA MEGA COMBO!", THEME["yellow"], 2.0)
        trigger_shake(8)

def reset_combo():
    if state["combo"] > 0:
        state["combo"] = 0
        dom["combo"].innerText = "0"

def init_pegs(difficulty):
    pegs.clear()
    
    layouts = ["grid", "pyramid", "diamond", "staggered", "honeycomb"]
    layout_type = layouts[state["layout_index"] % len(layouts)]
    state["layout_index"] += 1 
    
    start_y = 100
    
    if difficulty == 'easy':
        rows = 6
        if layout_type == "grid":
            for r in range(rows):
                cols = 5
                total_width = CANVAS_W - 80
                for c in range(cols):
                    px = 40 + (c * (total_width / (cols - 1)))
                    py = start_y + (r * 45)
                    pegs.append({"x": px, "y": py, "radius": 7, "hit": 0, "vx": 0, "ox": px, "moving": False})
        elif layout_type == "pyramid":
            for r in range(rows):
                cols = r + 2
                start_x = (CANVAS_W - ((cols - 1) * 40)) / 2
                for c in range(cols):
                    px = start_x + (c * 40)
                    py = start_y + (r * 45)
                    pegs.append({"x": px, "y": py, "radius": 7, "hit": 0, "vx": 0, "ox": px, "moving": False})
        elif layout_type == "diamond":
            pattern_cols = [3, 5, 6, 5, 3, 4]
            for r, cols in enumerate(pattern_cols):
                total_width = CANVAS_W - 80
                for c in range(cols):
                    px = 40 + (c * (total_width / (cols - 1))) if cols > 1 else CANVAS_W / 2
                    py = start_y + (r * 45)
                    pegs.append({"x": px, "y": py, "radius": 7, "hit": 0, "vx": 0, "ox": px, "moving": False})
        elif layout_type == "staggered":
            for r in range(rows):
                cols = 5 if r % 2 == 0 else 4
                total_width = CANVAS_W - 70
                start_x = 35 if r % 2 == 0 else 55
                for c in range(cols):
                    px = start_x + (c * (total_width / (cols - 1))) if cols > 1 else CANVAS_W / 2
                    py = start_y + (r * 45)
                    pegs.append({"x": px, "y": py, "radius": 7, "hit": 0, "vx": 0, "ox": px, "moving": False})
        else:
            for r in range(rows):
                cols = 5 if r % 2 == 0 else 4
                start_x = 45 if r % 2 == 0 else 65
                for c in range(cols):
                    px = start_x + (c * 50)
                    py = start_y + (r * 45)
                    if px <= CANVAS_W - 30:
                        pegs.append({"x": px, "y": py, "radius": 7, "hit": 0, "vx": 0, "ox": px, "moving": False})
    else:
        rows = 8
        if layout_type == "grid":
            for r in range(rows):
                cols = 7
                total_width = CANVAS_W - 50
                moving = True
                speed = 1.6
                for c in range(cols):
                    px = 25 + (c * (total_width / (cols - 1)))
                    py = start_y + (r * 36)
                    s = speed if c % 2 == 0 else -speed
                    pegs.append({"x": px, "y": py, "radius": 5.5, "hit": 0, "vx": s, "ox": px, "moving": moving})
        elif layout_type == "pyramid":
            for r in range(rows):
                cols = r + 3
                start_x = (CANVAS_W - ((cols - 1) * 35)) / 2
                moving = True
                speed = 1.8
                for c in range(cols):
                    px = start_x + (c * 35)
                    py = start_y + (r * 36)
                    s = -speed if c % 2 == 0 else speed
                    pegs.append({"x": px, "y": py, "radius": 5.5, "hit": 0, "vx": s, "ox": px, "moving": moving})
        elif layout_type == "diamond":
            pattern_cols = [3, 5, 7, 8, 7, 5, 4, 6]
            for r, cols in enumerate(pattern_cols):
                total_width = CANVAS_W - 50
                moving = True
                speed = 2.0
                for c in range(cols):
                    px = 25 + (c * (total_width / (cols - 1))) if cols > 1 else CANVAS_W / 2
                    py = start_y + (r * 36)
                    s = speed if c % 2 == 0 else -speed
                    pegs.append({"x": px, "y": py, "radius": 5.5, "hit": 0, "vx": s, "ox": px, "moving": moving})
        elif layout_type == "staggered":
            for r in range(rows):
                cols = 7 if r % 2 == 0 else 6
                total_width = CANVAS_W - 50
                start_x = 25 if r % 2 == 0 else 40
                moving = True
                speed = 1.7
                for c in range(cols):
                    px = start_x + (c * (total_width / (cols - 1))) if cols > 1 else CANVAS_W / 2
                    py = start_y + (r * 36)
                    s = -speed if c % 2 != 0 else speed
                    pegs.append({"x": px, "y": py, "radius": 5.5, "hit": 0, "vx": s, "ox": px, "moving": moving})
        else:
            for r in range(rows):
                cols = 6 if r % 2 == 0 else 7
                start_x = 30 if r % 2 == 0 else 15
                moving = True
                speed = 1.9
                for c in range(cols):
                    px = start_x + (c * 42)
                    py = start_y + (r * 36)
                    if px <= CANVAS_W - 15:
                        s = speed if c % 2 == 0 else -speed
                        pegs.append({"x": px, "y": py, "radius": 5.5, "hit": 0, "vx": s, "ox": px, "moving": moving})

def start_game(e):
    global mission
    state["layout_index"] = 0 
    diff = getattr(js, "selectedDifficulty", "easy")
    init_pegs(diff)
    
    mission = generate_mission()
    dom["mission_text"].innerText = mission["desc"]
    dom["mission_fill"].style.width = "0%"
    dom["mission_fill"].style.background = THEME["blue"]
    dom["mission_fill"].style.boxShadow = f"0 0 8px {THEME['blue']}"
    
    state["status"] = "PLAYING"
    state["score"] = 0
    state["energy"] = 30
    state["combo"] = 0
    state["max_combo"] = 0
    state["total_bounces"] = 0
    state["missions_cleared"] = 0
    
    balls.clear()
    particles.clear()
    floating_texts.clear()
    
    add_score(0)
    dom["energy"].innerText = str(state["energy"])
    dom["combo"].innerText = "0"
    dom["overlay"].classList.remove("active")

def open_menu(e):
    resume_btn = ensure_resume_button()
    
    if state["status"] == "PLAYING":
        state["status"] = "PAUSED"
        resume_btn.style.display = "block" # Tampilkan tombol Lanjutkan
    else:
        resume_btn.style.display = "none"  # Sembunyikan jika dari awal/game over
        
    dom["overlay"].classList.add("active")
    dom["overlay_title"].innerText = "PHYSIC GAME"
    dom["overlay_desc"].innerText = "Pilih tingkat keramaian rintangan:"
    dom["menu_mode"].style.display = "flex"
    dom["go_content"].style.display = "none"
    dom["btn_start"].innerText = "MULAI MAIN"

def resume_game(e):
    if state["status"] == "PAUSED":
        state["status"] = "PLAYING"
        dom["overlay"].classList.remove("active")
        ensure_resume_button().style.display = "none"

def show_game_over():
    state["status"] = "GAMEOVER"
    rank, color = get_rank()
    
    resume_btn = ensure_resume_button()
    resume_btn.style.display = "none"
    
    dom["overlay"].classList.add("active")
    dom["overlay_title"].innerText = "PERMAINAN SELESAI"
    dom["overlay_desc"].innerText = "Skor Akhir Kamu:"
    dom["menu_mode"].style.display = "none"
    dom["go_content"].style.display = "block"
    
    dom["go_rank"].innerText = rank
    dom["go_rank"].style.color = color
    dom["go_score"].innerText = str(state["score"])
    dom["go_combo"].innerText = str(state["max_combo"])
    dom["go_bounce"].innerText = str(state["total_bounces"])
    
    dom["go_mission"].innerText = f"{state['missions_cleared']} Misi"
    dom["go_mission"].style.color = THEME["cyan"] if state['missions_cleared'] > 0 else THEME["pink"]
        
    dom["btn_start"].innerText = "MAIN LAGI"

def spawn_ball(x, y):
    if state["energy"] <= 0: return
    state["energy"] -= 1
    dom["energy"].innerText = str(state["energy"])
    
    balls.append({
        "x": x, "y": y,
        "vx": random.uniform(-1.0, 1.0), "vy": random.uniform(0, 1),
        "radius": 7.5, "color": random.choice(COLORS), "trail": [],
        "bounces": 0
    })

def handle_touch(e):
    if state["status"] != "PLAYING": return
    
    rect = canvas.getBoundingClientRect()
    if hasattr(e, 'touches') and e.touches.length > 0:
        x = e.touches.item(0).clientX - rect.left
        y = e.touches.item(0).clientY - rect.top
    else:
        x = e.clientX - rect.left
        y = e.clientY - rect.top

    if y > SPAWN_ZONE_H: return

    if state["burst_mode"]:
        for _ in range(3):
            if state["energy"] > 0:
                spawn_ball(x + random.uniform(-12, 12), y + random.uniform(-5, 5))
    else: spawn_ball(x, y)

def toggle_mode(e):
    state["burst_mode"] = not state["burst_mode"]
    dom["btn_mode"].innerText = "Mode: Lempar 3x" if state["burst_mode"] else "Mode: Lempar 1x"

# --- FISIKA & UPDATE ---
def update_physics():
    active_balls = []
    
    for b in balls:
        b["trail"].append({"x": b["x"], "y": b["y"]})
        if len(b["trail"]) > 6: b["trail"].pop(0)

        b["vy"] += GRAVITY
        b["x"] += b["vx"]
        b["y"] += b["vy"]
        r = b["radius"]

        if b["x"] + r > CANVAS_W:
            b["x"] = CANVAS_W - r
            b["vx"] *= BOUNCINESS
            b["vy"] += 0.2
        elif b["x"] - r < 0:
            b["x"] = r
            b["vx"] *= BOUNCINESS
            b["vy"] += 0.2

        for peg in pegs:
            dx = b["x"] - peg["x"]
            dy = b["y"] - peg["y"]
            dist = math.hypot(dx, dy)
            min_dist = r + peg["radius"]
            
            if dist < min_dist:
                angle = math.atan2(dy, dx) + random.uniform(-0.04, 0.04)
                b["x"] = peg["x"] + math.cos(angle) * min_dist
                b["y"] = peg["y"] + math.sin(angle) * min_dist
                
                b["bounces"] += 1
                
                if b["bounces"] > 45:
                    b["vx"] *= 0.5
                    b["vy"] = abs(b["vy"]) + 1.5
                    continue
                
                speed = math.hypot(b["vx"], b["vy"]) * 0.65 + 1.5
                speed = min(speed, 7.5) 
                
                b["vx"] = math.cos(angle) * speed
                b["vy"] = math.sin(angle) * speed
                
                peg["hit"] = 1.0
                spawn_particles(peg["x"], peg["y"], b["color"], 4, 2.0)
                
                state["total_bounces"] += 1
                update_mission("bounce", 1)
                handle_combo()
                
                mult = 1
                if state["combo"] >= 25: mult = 5
                elif state["combo"] >= 10: mult = 3
                elif state["combo"] >= 5: mult = 2
                
                pts = 5 * mult
                add_score(pts)
                
                if random.random() > 0.6: 
                    spawn_floating_text(peg["x"], peg["y"]-10, f"+{pts}", THEME["cyan"], 0.8)

        destroyed = False
        if b["y"] + r > CANVAS_H - BUCKET_H:
            idx = max(0, min(int(b["x"] / ZONE_W), len(ZONES) - 1))
            z = ZONES[idx]
            
            add_score(z["score"])
            
            if z["bonus"] > 0:
                state["energy"] += z["bonus"]
                dom["energy"].innerText = str(state["energy"])
                update_mission("zone500", 1)
                spawn_floating_text(b["x"], CANVAS_H - BUCKET_H - 30, "DAPAT ENERGI!", THEME["yellow"], 1.5)
                trigger_shake(6)
            
            spawn_particles(b["x"], CANVAS_H - BUCKET_H/2, z["color"], 18, 4.5)
            spawn_floating_text(b["x"], CANVAS_H - BUCKET_H + 10, f"+{z['score']}", z["color"], 1.2)
            destroyed = True

        if not destroyed: active_balls.append(b)

    balls.clear()
    balls.extend(active_balls)

    for peg in pegs:
        if peg["moving"]:
            peg["x"] += peg["vx"]
            limit_range = 16 if getattr(js, "selectedDifficulty", "easy") == 'easy' else 22
            if abs(peg["x"] - peg["ox"]) > limit_range: peg["vx"] *= -1
        if peg["hit"] > 0: peg["hit"] -= 0.05

    if state["combo_timer"] > 0:
        state["combo_timer"] -= 1
        if state["combo_timer"] <= 0: reset_combo()

def update_effects():
    active_p = []
    for p in particles:
        p["x"] += p["vx"]
        p["y"] += p["vy"]
        p["life"] -= p["decay"]
        if p["life"] > 0: active_p.append(p)
    particles.clear()
    particles.extend(active_p)
    
    active_ft = []
    for ft in floating_texts:
        ft["y"] += ft["vy"]
        ft["life"] -= 0.02
        if ft["life"] > 0: active_ft.append(ft)
    floating_texts.clear()
    floating_texts.extend(active_ft)

# --- RENDERING ---
def render():
    ctx.clearRect(0, 0, CANVAS_W, CANVAS_H)
    
    ctx.fillStyle = "rgba(255, 255, 255, 0.02)"
    ctx.fillRect(0, 0, CANVAS_W, SPAWN_ZONE_H)
    ctx.beginPath()
    ctx.setLineDash([4, 4])
    ctx.moveTo(0, SPAWN_ZONE_H)
    ctx.lineTo(CANVAS_W, SPAWN_ZONE_H)
    ctx.strokeStyle = "rgba(0, 245, 212, 0.3)"
    ctx.lineWidth = 1
    ctx.stroke()
    ctx.setLineDash([])
    
    ctx.fillStyle = "rgba(255, 255, 255, 0.3)"
    ctx.font = "bold 10px sans-serif"
    ctx.textAlign = "center"
    ctx.fillText("AREA LEMPAR BOLA (TAP/KLIK DI SINI)", CANVAS_W/2, SPAWN_ZONE_H - 10)

    for i, z in enumerate(ZONES):
        bx = i * ZONE_W
        by = CANVAS_H - BUCKET_H
        
        ctx.shadowBlur = 10
        ctx.shadowColor = z["color"]
        
        ctx.fillStyle = "rgba(10, 10, 25, 0.9)"
        ctx.fillRect(bx, by, ZONE_W, BUCKET_H)
        
        ctx.strokeStyle = z["color"]
        ctx.lineWidth = 1.5
        ctx.strokeRect(bx, by, ZONE_W, BUCKET_H)
        
        ctx.shadowBlur = 0
        ctx.fillStyle = z["color"]
        ctx.font = "bold 13px sans-serif"
        
        lines = z["label"].split('\n')
        for li, line in enumerate(lines):
            ctx.fillText(line, bx + ZONE_W/2, by + 18 + (li * 15))

    for peg in pegs:
        ctx.beginPath()
        ctx.arc(peg["x"], peg["y"], peg["radius"], 0, js.Math.PI * 2)
        
        glow = peg["hit"]
        base_color = THEME["pink"] if peg["moving"] else THEME["cyan"]
        
        ctx.fillStyle = f"rgba(255, 255, 255, {0.1 + glow * 0.5})"
        ctx.fill()
        
        if glow > 0:
            ctx.shadowBlur = 15 * glow
            ctx.shadowColor = base_color
            
        ctx.strokeStyle = base_color
        ctx.lineWidth = 2 + (glow * 2)
        ctx.stroke()
        ctx.shadowBlur = 0

    for b in balls:
        if len(b["trail"]) > 1:
            ctx.beginPath()
            ctx.moveTo(b["trail"][0]["x"], b["trail"][0]["y"])
            for t in b["trail"][1:]: ctx.lineTo(t["x"], t["y"])
            ctx.strokeStyle = b["color"]
            ctx.lineWidth = b["radius"] * 1.2
            ctx.globalAlpha = 0.25
            ctx.stroke()
            ctx.globalAlpha = 1.0

        ctx.beginPath()
        ctx.arc(b["x"], b["y"], b["radius"], 0, js.Math.PI * 2)
        ctx.fillStyle = b["color"]
        ctx.shadowBlur = 12
        ctx.shadowColor = b["color"]
        ctx.fill()
        
        ctx.fillStyle = "rgba(255,255,255,0.8)"
        ctx.beginPath()
        ctx.arc(b["x"] - 2, b["y"] - 2, 2, 0, js.Math.PI * 2)
        ctx.fill()
        ctx.shadowBlur = 0

    for p in particles:
        ctx.beginPath()
        ctx.arc(p["x"], p["y"], p["size"], 0, js.Math.PI * 2)
        ctx.fillStyle = p["color"]
        ctx.globalAlpha = p["life"]
        ctx.fill()
    ctx.globalAlpha = 1.0

    for ft in floating_texts:
        ctx.fillStyle = ft["color"]
        ctx.globalAlpha = ft["life"]
        ctx.font = f"bold {int(12 * ft['scale'])}px sans-serif"
        ctx.shadowBlur = 8
        ctx.shadowColor = ft["color"]
        ctx.fillText(ft["text"], ft["x"], ft["y"])
    ctx.globalAlpha = 1.0
    ctx.shadowBlur = 0

def game_loop(*args):
    if state["status"] == "PLAYING":
        update_physics()
        update_effects()
        apply_shake()
        
        if state["energy"] <= 0 and len(balls) == 0 and len(particles) == 0:
            show_game_over()
            
    if state["status"] in ["PLAYING", "START", "PAUSED"]:
        render()
        
    js.window.requestAnimationFrame(proxy_loop)

# --- BINDING EVENT ---
proxy_loop = create_proxy(game_loop)
canvas.addEventListener("pointerdown", create_proxy(handle_touch))
dom["btn_start"].addEventListener("click", create_proxy(start_game))
dom["btn_mode"].addEventListener("click", create_proxy(toggle_mode))
dom["btn_menu"].addEventListener("click", create_proxy(open_menu))

js.window.requestAnimationFrame(proxy_loop)
