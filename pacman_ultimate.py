import pygame
import random
import sys
import math
import json
import os
from collections import deque

# ==================== НАСТРОЙКИ ====================
TILE_SIZE = 28
COLS = 19
ROWS = 21
HUD_HEIGHT = 60
WIDTH = COLS * TILE_SIZE
HEIGHT = ROWS * TILE_SIZE + HUD_HEIGHT
FPS = 60
MOVE_DELAY_BASE = 8       # кадров на шаг (меньше = быстрее)
MOVE_DELAY_FRIGHT = 12    # медленнее в испуге
FRIGHT_TIME = 8 * FPS     # кадров испуга
SCATTER_TIME = 7 * FPS    # кадров разбегания
CHASE_TIME = 20 * FPS     # кадров погони
SAVE_FILE = "pacman_save.json"

# ==================== ЦВЕТА ====================
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
YELLOW = (255, 255, 0)
DARK_YELLOW = (200, 200, 0)
BLUE = (33, 33, 222)
DARK_BLUE = (0, 0, 120)
WALL_GLOW = (60, 60, 255)
PELLET_COLOR = (255, 220, 160)
POWER_COLOR = (255, 255, 180)
RED = (255, 0, 0)
PINK = (255, 184, 255)
ORANGE = (255, 165, 0)
CYAN = (0, 255, 255)
FRIGHT_BLUE = (36, 36, 200)
FRIGHT_FLASH = (255, 255, 255)
GHOST_EYE = (255, 255, 255)
GHOST_PUPIL = (0, 0, 255)

DIRS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}
DIR_LIST = list(DIRS.values())

# ==================== КАРТА ====================
# # стена, . точка, o энергайзер, F фрукт, P спавн пакмана, пробел - пусто
# G - спавн призраков (заменяется на пусто)
MAP_TEMPLATE = [
    "###################",
    "#........#........#",
    "#o##.###.#.###.##o#",
    "#.................#",
    "#.##.#.#####.#.##.#",
    "#....#...#...#....#",
    "####.### # ###.####",
    "   #.#   G   #.#   ",
    "####.# ##-## #.####",
    "    .  #   #  .    ",
    "####.# ##### #.####",
    "   #.#       #.#   ",
    "####.# ##### #.####",
    "#........#........#",
    "#.##.###.#.###.##.#",
    "#o.#.....P.....#.o#",
    "##.#.#.#####.#.#.##",
    "#....#...#...#....#",
    "#.######.#.######.#",
    "#.................#",
    "###################",
]

# ==================== ВСПОМОГАТЕЛЬНОЕ ====================
def load_grid():
    grid = []
    spawn = None
    ghost_spawns = []
    for r, row in enumerate(MAP_TEMPLATE):
        line = []
        for c, ch in enumerate(row):
            if ch == '#':
                line.append(1)
            elif ch == '.':
                line.append(2)
            elif ch == 'o':
                line.append(3)
            elif ch == 'F':
                line.append(4)
            elif ch == 'P':
                line.append(0)
                spawn = (c, r)
            elif ch == 'G':
                line.append(0)
                ghost_spawns.append((c, r))
            else:
                line.append(0)
        grid.append(line)
    return grid, spawn, ghost_spawns

def count_pellets(grid):
    return sum(cell in (2, 3, 4) for row in grid for cell in row)

def draw_circle_aa(surface, color, pos, radius):
    """Сглаженный круг"""
    pygame.draw.circle(surface, color, pos, radius)

def lerp_color(c1, c2, t):
    t = max(0, min(1, t))
    return (int(c1[0] + (c2[0]-c1[0])*t),
            int(c1[1] + (c2[1]-c1[1])*t),
            int(c1[2] + (c2[2]-c1[2])*t))

# ==================== BFS для поиска пути ====================
def bfs_next_step(start, target, grid):
    """Возвращает направление к target, обходя стены (BFS)."""
    if start == target:
        return (0, 0)
    q = deque([start])
    visited = {start: None}
    while q:
        cur = q.popleft()
        if cur == target:
            break
        for d in DIR_LIST:
            nxt = (cur[0]+d[0], cur[1]+d[1])
            if 0 <= nxt[1] < ROWS and 0 <= nxt[0] < COLS \
               and nxt not in visited and grid[nxt[1]][nxt[0]] != 1:
                visited[nxt] = cur
                q.append(nxt)
    if target not in visited:
        return (0, 0)
    # восстановим путь
    path = []
    cur = target
    while cur != start:
        path.append(cur)
        cur = visited[cur]
    path.reverse()
    if not path:
        return (0, 0)
    first = path[0]
    return (first[0]-start[0], first[1]-start[1])

# ==================== ПАКМАН ====================
class Pacman:
    def __init__(self, spawn):
        self.start_x, self.start_y = spawn
        self.reset()

    def reset(self):
        self.x, self.y = self.start_x, self.start_y
        self.dir = (0, 0)
        self.next_dir = (0, 0)
        self.anim_frame = 0
        self.mouth_open = 1.0
        self.eaten = 0  # сколько накоплено очков за тик

    def can_move(self, x, y, grid):
        if not (0 <= y < ROWS and 0 <= x < COLS):
            return False
        return grid[y][x] != 1

    def update(self, grid):
        self.eaten = 0

        # Попытка поворота
        if self.next_dir != (0, 0):
            nx = self.x + self.next_dir[0]
            ny = self.y + self.next_dir[1]
            if self.can_move(nx, ny, grid):
                self.dir = self.next_dir
                self.next_dir = (0, 0)

        # Движение
        if self.dir != (0, 0):
            nx = self.x + self.dir[0]
            ny = self.y + self.dir[1]
            if self.can_move(nx, ny, grid):
                self.x, self.y = nx, ny
            else:
                self.dir = (0, 0)

        # Телепорт через боковые туннели
        if self.x < 0:
            self.x = COLS - 1
        elif self.x >= COLS:
            self.x = 0

        # Съедание
        cell = grid[self.y][self.x]
        if cell == 2:
            grid[self.y][self.x] = 0
            self.eaten = 10
        elif cell == 3:
            grid[self.y][self.x] = 0
            self.eaten = 50
        elif cell == 4:
            grid[self.y][self.x] = 0
            self.eaten = 100

        # Анимация рта
        self.anim_frame = (self.anim_frame + 1) % 20
        if self.anim_frame < 10:
            self.mouth_open = self.anim_frame / 10
        else:
            self.mouth_open = (20 - self.anim_frame) / 10


# ==================== ПРИЗРАК ====================
class Ghost:
    def __init__(self, spawn, color, name):
        self.start_x, self.start_y = spawn
        self.color = color
        self.name = name
        self.reset()

    def reset(self):
        self.x, self.y = self.start_x, self.start_y
        self.dir = random.choice(DIR_LIST)
        self.frightened = False
        self.eaten = False  # съеден -> летит домой
        self.anim = 0
        self.in_house = True
        self.release_timer = 60 + random.randint(0, 120)

    def release(self):
        self.in_house = False

    def update(self, grid, pacman, mode, ghosts, blinky):
        self.anim = (self.anim + 1) % 20

        # Таймер выхода из дома
        if self.in_house:
            self.release_timer -= 1
            if self.release_timer <= 0:
                self.in_house = False
                # выходим вверх
                self.x, self.y = self.start_x, self.start_y - 1
                self.dir = (0, -1)
                return

        # Скорость зависит от состояния
        delay = MOVE_DELAY_FRIGHT if self.frightened else MOVE_DELAY_BASE
        # (в основной игре скорость управляется снаружи через счётчик)

        # Выбор направления
        target = self.get_target(pacman, mode, ghosts, blinky)
        if target is not None:
            d = bfs_next_step((self.x, self.y), target, grid)
            if d != (0, 0) and not self._reverse(d):
                self.dir = d
            else:
                # если BFS не дал хода — перебор
                options = [dd for dd in DIR_LIST
                           if not self._reverse(dd)
                           and self._can(self.x+dd[0], self.y+dd[1], grid)]
                if options:
                    self.dir = random.choice(options)
        else:
            # случайное блуждание
            options = [dd for dd in DIR_LIST
                       if not self._reverse(dd)
                       and self._can(self.x+dd[0], self.y+dd[1], grid)]
            if options:
                self.dir = random.choice(options)

        # Движение
        nx, ny = self.x + self.dir[0], self.y + self.dir[1]
        if self._can(nx, ny, grid):
            self.x, self.y = nx, ny
        else:
            self.dir = (0, 0)

        # Телепорт
        if self.x < 0:
            self.x = COLS - 1
        elif self.x >= COLS:
            self.x = 0

    def _can(self, x, y, grid):
        if not (0 <= y < ROWS and 0 <= x < COLS):
            return False
        return grid[y][x] != 1

    def _reverse(self, d):
        return d == (-self.dir[0], -self.dir[1])

    def get_target(self, pacman, mode, ghosts, blinky):
        """Возвращает целевую клетку (или None для случайного)."""
        if self.frightened or self.eaten:
            return None  # случайное движение

        px, py = pacman.x, pacman.y
        pd = pacman.dir

        if mode == "scatter":
            # углы карты
            corners = {
                "red": (COLS-2, 0),
                "pink": (1, 0),
                "cyan": (COLS-2, ROWS-1),
                "orange": (1, ROWS-1),
            }
            return corners.get(self.name)

        # chase
        if self.name == "red":
            return (px, py)
        elif self.name == "pink":
            return (px + pd[0]*4, py + pd[1]*4)
        elif self.name == "cyan":
            # вектор от red к 2 клеткам впереди пакмана, удвоенный
            tx = px + pd[0]*2
            ty = py + pd[1]*2
            if blinky:
                return (tx*2 - blinky.x, ty*2 - blinky.y)
            return (tx, ty)
        elif self.name == "orange":
            dx = self.x - px
            dy = self.y - py
            if dx*dx + dy*dy > 64:  # >8 клеток
                return (px, py)
            return (1, ROWS-1)
        return (px, py)


# ==================== ЧАСТИЦЫ ====================
class Particle:
    def __init__(self, x, y, color, vx=None, vy=None, life=30, size=4):
        self.x = x
        self.y = y
        self.vx = vx if vx is not None else random.uniform(-3, 3)
        self.vy = vy if vy is not None else random.uniform(-3, 3)
        self.life = life
        self.max_life = life
        self.color = color
        self.size = size

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.1
        self.life -= 1

    def draw(self, surf, camera_offset=(0, 0)):
        if self.life <= 0:
            return
        t = self.life / self.max_life
        r = max(1, int(self.size * t))
        c = lerp_color((0, 0, 0), self.color, t)
        pygame.draw.circle(surf, c, (int(self.x), int(self.y)), r)


class FloatingText:
    def __init__(self, x, y, text, color=WHITE, life=50):
        self.x, self.y = x, y
        self.text = text
        self.color = color
        self.life = life
        self.max_life = life

    def update(self):
        self.y -= 0.8
        self.life -= 1

    def draw(self, surf, font):
        if self.life <= 0:
            return
        t = self.life / self.max_life
        c = lerp_color(BLACK, self.color, t)
        s = font.render(self.text, True, c)
        surf.blit(s, (int(self.x) - s.get_width()//2, int(self.y)))


# ==================== ЗВУКИ (заглушки) ====================
class SoundManager:
    """Простая генерация звуков через pygame.mixer (если есть)."""
    def __init__(self):
        self.enabled = False
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=1)
            self.enabled = True
            self.sounds = {}
            self._generate()
        except Exception:
            pass

    def _make_sound(self, freq, duration_ms, volume=0.2):
        import array
        try:
            sample_rate = 22050
            n = int(sample_rate * duration_ms / 1000)
            buf = array.array('h')
            for i in range(n):
                t = i / sample_rate
                # затухание
                env = 1 - (i / n)
                val = int(32767 * volume * env * math.sin(2 * math.pi * freq * t))
                buf.append(val)
            return pygame.mixer.Sound(buffer=buf.tobytes())
        except Exception:
            return None

    def _generate(self):
        self.sounds['chomp'] = self._make_sound(440, 60, 0.15)
        self.sounds['power'] = self._make_sound(660, 150, 0.25)
        self.sounds['death'] = self._make_sound(150, 400, 0.3)
        self.sounds['eat_ghost'] = self._make_sound(880, 200, 0.3)
        self.sounds['fruit'] = self._make_sound(1200, 150, 0.25)
        self.sounds['level'] = self._make_sound(1000, 300, 0.3)
        self.sounds['start'] = self._make_sound(550, 200, 0.25)

    def play(self, name):
        if self.enabled and name in self.sounds and self.sounds[name]:
            try:
                self.sounds[name].play()
            except Exception:
                pass


# ==================== ИГРА ====================
class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Pac-Man ULTIMATE")
        self.clock = pygame.time.Clock()
        self.font_small = pygame.font.SysFont("consolas", 16, bold=True)
        self.font_med = pygame.font.SysFont("consolas", 22, bold=True)
        self.font_big = pygame.font.SysFont("consolas", 44, bold=True)
        self.font_title = pygame.font.SysFont("consolas", 56, bold=True)
        self.sound = SoundManager()

        self.high_score = self.load_high_score()
        self.particles = []
        self.floaters = []
        self.shake_time = 0
        self.flash_time = 0
        self.flash_color = WHITE
        self.combo = 0
        self.combo_timer = 0

        # Скины (циклично переключаются по S)
        self.skin = 0
        self.skins = [
            {"name": "Classic", "pac": YELLOW, "wall": BLUE},
            {"name": "Neon", "pac": (0, 255, 200), "wall": (200, 0, 255)},
            {"name": "Fire", "pac": (255, 120, 0), "wall": (120, 0, 0)},
            {"name": "Ice", "pac": (150, 220, 255), "wall": (30, 60, 120)},
        ]

        self.show_minimap = True
        self.paused = False
        self.help_open = False

        self.reset_game(load_save=False)

    # -------- Сохранения --------
    def load_high_score(self):
        try:
            if os.path.exists(SAVE_FILE):
                with open(SAVE_FILE) as f:
                    return json.load(f).get("high_score", 0)
        except Exception:
            pass
        return 0

    def save_high_score(self):
        try:
            with open(SAVE_FILE, "w") as f:
                json.dump({"high_score": self.high_score}, f)
        except Exception:
            pass

    # -------- Сброс --------
    def reset_game(self, load_save=False):
        self.grid, self.pac_spawn, self.ghost_spawns = load_grid()
        self.ghost_spawns = self.ghost_spawns or [(9, 7), (8, 7), (10, 7), (9, 8)]

        self.pacman = Pacman(self.pac_spawn)
        colors = [RED, PINK, CYAN, ORANGE]
        names = ["red", "pink", "cyan", "orange"]
        self.ghosts = []
        for i in range(4):
            spawn = self.ghost_spawns[i] if i < len(self.ghost_spawns) else (9, 7)
            self.ghosts.append(Ghost(spawn, colors[i], names[i]))

        self.score = 0
        self.lives = 3
        self.level = 1
        self.total_pellets = count_pellets(self.grid)
        self.pellets_left = self.total_pellets
        self.state = "playing"
        self.move_counter = 0
        self.pac_delay = MOVE_DELAY_BASE
        self.ghost_delays = [MOVE_DELAY_BASE]*4
        self.ghost_counters = [0]*4

        self.fright_timer = 0
        self.mode_timer = SCATTER_TIME
        self.mode = "scatter"
        self.fruit = None
        self.fruit_timer = 0
        self.particles = []
        self.floaters = []
        self.combo = 0
        self.combo_timer = 0
        self.level_msg_timer = 120

        # BFS-оптимизация: обновляем не каждый тик
        self.ai_tick = 0

    # -------- Фрукты --------
    def try_spawn_fruit(self):
        if self.fruit is not None:
            return
        # фрукт появляется когда съедено ~70 точек и потом ещё 170
        eaten = self.total_pellets - self.pellets_left
        if eaten in (70, 170):
            # ставим в случайную пустую клетку
            empty = [(c, r) for r in range(1, ROWS-1) for c in range(1, COLS-1)
                     if self.grid[r][c] == 0]
            if empty:
                fx, fy = random.choice(empty)
                self.fruit = (fx, fy)
                self.fruit_timer = 10 * FPS

    def draw_fruit(self):
        if not self.fruit:
            return
        fx, fy = self.fruit
        cx = fx*TILE_SIZE + TILE_SIZE//2
        cy = fy*TILE_SIZE + TILE_SIZE//2
        pulse = 1 + math.sin(pygame.time.get_ticks()/150)*0.2
        r = int(TILE_SIZE*0.35*pulse)
        pygame.draw.circle(self.screen, RED, (cx, cy), r)
        pygame.draw.circle(self.screen, (0, 150, 0), (cx, cy - r), max(2, r//2))

    # -------- Ввод --------
    def handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.save_high_score()
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                k = event.key
                if k == pygame.K_UP or k == pygame.K_w:
                    self.pacman.next_dir = (0, -1)
                elif k == pygame.K_DOWN or k == pygame.K_s:
                    self.pacman.next_dir = (0, 1)
                elif k == pygame.K_LEFT or k == pygame.K_a:
                    self.pacman.next_dir = (-1, 0)
                elif k == pygame.K_RIGHT or k == pygame.K_d:
                    self.pacman.next_dir = (1, 0)
                elif k == pygame.K_SPACE:
                    self.paused = not self.paused
                elif k == pygame.K_r:
                    self.reset_game()
                elif k == pygame.K_h or k == pygame.K_F1:
                    self.help_open = not self.help_open
                    if self.help_open: self.paused = True
                elif k == pygame.K_m:
                    self.show_minimap = not self.show_minimap
                elif k == pygame.K_TAB:
                    self.skin = (self.skin + 1) % len(self.skins)
                elif k == pygame.K_p:
                    self.save_high_score()
                    self.flash_screen(GREEN if False else WHITE)
                elif k == pygame.K_ESCAPE:
                    self.save_high_score()
                    pygame.quit()
                    sys.exit()

    # -------- Обновление --------
    def update(self):
        if self.paused or self.help_open:
            return
        if self.state == "dead":
            self.update_particles()
            self.dead_timer -= 1
            if self.dead_timer <= 0:
                if self.lives > 0:
                    self.pacman.reset()
                    for g in self.ghosts:
                        g.reset()
                    self.mode = "scatter"
                    self.mode_timer = SCATTER_TIME
                    self.fright_timer = 0
                    self.state = "playing"
                else:
                    self.state = "gameover"
                    if self.score > self.high_score:
                        self.high_score = self.score
                        self.save_high_score()
            return
        if self.state in ("gameover", "win"):
            self.update_particles()
            return

        # Таймер испуга
        if self.fright_timer > 0:
            self.fright_timer -= 1
            if self.fright_timer <= 0:
                for g in self.ghosts:
                    g.frightened = False

        # Смена режима
        if self.fright_timer == 0:
            self.mode_timer -= 1
            if self.mode_timer <= 0:
                if self.mode == "scatter":
                    self.mode = "chase"
                    self.mode_timer = CHASE_TIME
                else:
                    self.mode = "scatter"
                    self.mode_timer = SCATTER_TIME

        # Комбо-таймер
        if self.combo_timer > 0:
            self.combo_timer -= 1
            if self.combo_timer <= 0:
                self.combo = 0

        # Pac-Man (по своему таймеру)
        self.move_counter += 1
        pac_delay = self.pac_delay
        if self.move_counter >= pac_delay:
            self.move_counter = 0
            before = self.pellets_left
            self.pacman.update(self.grid)
            # начисление очков
            if self.pacman.eaten:
                self.score += self.pacman.eaten + self.combo * 2
                self.pellets_left = count_pellets(self.grid)
                self.combo += 1
                self.combo_timer = FPS
                if self.pacman.eaten == 50:
                    self.trigger_fright()
                    self.spawn_particles(self.pacman.x, self.pacman.y, POWER_COLOR, 20)
                    self.sound.play('power')
                elif self.pacman.eaten == 10:
                    if self.combo % 3 == 0:
                        self.sound.play('chomp')
                elif self.pacman.eaten == 100:
                    self.sound.play('fruit')
                    self.floaters.append(FloatingText(
                        self.pacman.x*TILE_SIZE+TILE_SIZE//2,
                        self.pacman.y*TILE_SIZE,
                        "+100", YELLOW))
                    self.spawn_particles(self.pacman.x, self.pacman.y, YELLOW, 25)

                # счётчик клеток
                self.try_spawn_fruit()

        # Съедание фрукта
        if self.fruit and (self.pacman.x, self.pacman.y) == self.fruit:
            self.score += 100
            self.fruit = None
            self.spawn_particles(self.pacman.x, self.pacman.y, RED, 20)
            self.floaters.append(FloatingText(
                self.pacman.x*TILE_SIZE+TILE_SIZE//2,
                self.pacman.y*TILE_SIZE,
                "+100", RED))
            self.sound.play('fruit')

        if self.fruit:
            self.fruit_timer -= 1
            if self.fruit_timer <= 0:
                self.fruit = None

        # Призраки (по своим таймерам)
        blinky = next((g for g in self.ghosts if g.name == "red"), None)
        for i, g in enumerate(self.ghosts):
            delay = MOVE_DELAY_FRIGHT if g.frightened else MOVE_DELAY_BASE
            # если съеден и летит домой — быстрее
            if g.eaten:
                delay = max(3, MOVE_DELAY_BASE - 3)
            self.ghost_counters[i] += 1
            if self.ghost_counters[i] >= delay:
                self.ghost_counters[i] = 0
                g.update(self.grid, self.pacman, self.mode, self.ghosts, blinky)
                # долетел домой
                if g.eaten and (g.x, g.y) in [(sx, sy) for sx, sy in self.ghost_spawns]:
                    g.eaten = False
                    g.frightened = False

        # Столкновения
        for g in self.ghosts:
            if (g.x, g.y) == (self.pacman.x, self.pacman.y):
                if g.eaten:
                    continue
                if g.frightened:
                    self.score += 200 * (2 ** self.combo)
                    self.combo += 1
                    self.combo_timer = FPS
                    g.eaten = True
                    self.spawn_particles(g.x, g.y, g.color, 30)
                    self.floaters.append(FloatingText(
                        g.x*TILE_SIZE+TILE_SIZE//2, g.y*TILE_SIZE,
                        f"+{200*(2**(self.combo-1))}", CYAN))
                    self.sound.play('eat_ghost')
                else:
                    self.lives -= 1
                    self.state = "dead"
                    self.dead_timer = 45
                    self.shake_time = 20
                    self.flash_screen(RED)
                    self.spawn_particles(self.pacman.x, self.pacman.y, YELLOW, 40)
                    self.sound.play('death')
                    break

        # Победа
        self.pellets_left = count_pellets(self.grid)
        if self.pellets_left <= 0:
            self.state = "win"
            self.sound.play('level')
            self.flash_screen(YELLOW)

        # Обновляем частицы и всплывашки
        self.update_particles()

    def trigger_fright(self):
        self.fright_timer = FRIGHT_TIME
        for g in self.ghosts:
            if not g.eaten:
                g.frightened = True
                # разворачиваем
                g.dir = (-g.dir[0], -g.dir[1])
        self.combo = 0

    def spawn_particles(self, gx, gy, color, n):
        cx = gx*TILE_SIZE + TILE_SIZE//2
        cy = gy*TILE_SIZE + TILE_SIZE//2
        for _ in range(n):
            self.particles.append(Particle(cx, cy, color))

    def update_particles(self):
        for p in self.particles:
            p.update()
        self.particles = [p for p in self.particles if p.life > 0]
        for f in self.floaters:
            f.update()
        self.floaters = [f for f in self.floaters if f.life > 0]
        if self.shake_time > 0:
            self.shake_time -= 1
        if self.flash_time > 0:
            self.flash_time -= 1

    def flash_screen(self, color):
        self.flash_time = 8
        self.flash_color = color

    # -------- Отрисовка --------
    def draw(self):
        # смещение при тряске
        offset = (0, 0)
        if self.shake_time > 0:
            offset = (random.randint(-4, 4), random.randint(-4, 4))

        self.screen.fill(BLACK)

        skin = self.skins[self.skin]

        # Стены
        for r in range(ROWS):
            for c in range(COLS):
                cell = self.grid[r][c]
                x = c*TILE_SIZE + offset[0]
                y = r*TILE_SIZE + HUD_HEIGHT + offset[1]
                if cell == 1:
                    pygame.draw.rect(self.screen, skin["wall"], (x, y, TILE_SIZE, TILE_SIZE))
                    pygame.draw.rect(self.screen, WALL_GLOW, (x, y, TILE_SIZE, TILE_SIZE), 1)
                elif cell == 2:
                    pygame.draw.circle(self.screen, PELLET_COLOR,
                                       (x + TILE_SIZE//2, y + TILE_SIZE//2), 3)
                elif cell == 3:
                    pulse = int(2*math.sin(pygame.time.get_ticks()/150)) + 7
                    pygame.draw.circle(self.screen, POWER_COLOR,
                                       (x + TILE_SIZE//2, y + TILE_SIZE//2), pulse)

        # Фрукт
        if self.fruit:
            fx = self.fruit[0]*TILE_SIZE + offset[0] + TILE_SIZE//2
            fy = self.fruit[1]*TILE_SIZE + HUD_HEIGHT + offset[1] + TILE_SIZE//2
            pulse = 1 + math.sin(pygame.time.get_ticks()/150)*0.2
            r = int(TILE_SIZE*0.35*pulse)
            pygame.draw.circle(self.screen, RED, (fx, fy), r)
            pygame.draw.circle(self.screen, (0, 150, 0), (fx, fy - r), max(2, r//2))

        # Pac-Man
        self.draw_pacman(offset, skin)

        # Призраки
        for g in self.ghosts:
            self.draw_ghost(g, offset)

        # Частицы
        for p in self.particles:
            p.draw(self.screen, offset)
        for f in self.floaters:
            f.draw(self.screen, self.font_small)

        # Мини-карта
        if self.show_minimap:
            self.draw_minimap()

        # HUD
        self.draw_hud()

        # Flash
        if self.flash_time > 0:
            alpha = int(150 * (self.flash_time / 8))
            s = pygame.Surface((WIDTH, HEIGHT))
            s.set_alpha(alpha)
            s.fill(self.flash_color)
            self.screen.blit(s, (0, 0))

        # Пауза
        if self.paused and not self.help_open:
            self.draw_centered("PAUSED", YELLOW, self.font_big, -40)
            self.draw_centered("Press SPACE to continue", WHITE, self.font_med, 0)

        # Помощь
        if self.help_open:
            self.draw_help()

        # Game Over / Win
        if self.state == "gameover":
            self.draw_centered("GAME OVER", RED, self.font_title, -60)
            self.draw_centered(f"Score: {self.score}", WHITE, self.font_med, 0)
            self.draw_centered("Press R to restart", YELLOW, self.font_med, 40)
        elif self.state == "win":
            self.draw_centered("YOU WIN!", YELLOW, self.font_title, -60)
            self.draw_centered(f"Score: {self.score}", WHITE, self.font_med, 0)
            self.draw_centered("Press R to restart", YELLOW, self.font_med, 40)

        # Плашка уровня
        if self.level_msg_timer > 0:
            self.level_msg_timer -= 1
            self.draw_centered(f"LEVEL {self.level}", YELLOW, self.font_big, 60)

        pygame.display.flip()

    def draw_pacman(self, offset, skin):
        px = self.pacman.x * TILE_SIZE + offset[0] + TILE_SIZE // 2
        py = self.pacman.y * TILE_SIZE + HUD_HEIGHT + offset[1] + TILE_SIZE // 2
        r = TILE_SIZE // 2 - 2
        color = skin["pac"]

    # Направление (по умолчанию смотрим вправо)
        d = self.pacman.dir if self.pacman.dir != (0, 0) else (1, 0)
        base_angle = math.atan2(-d[1], d[0])  # в экранных координатах Y вниз -> минус

    # Угол раскрытия рта (0..1 -> 0..45°)
        mouth_angle = math.radians(45 * self.pacman.mouth_open)

    # Закрашиваем БОЛЬШУЮ дугу: от края рта (base+mouth) вокруг
    # до второго края рта (base-mouth), идём в положительном направлении
    # (по часовой стрелке в экранных координатах).
        start = base_angle + mouth_angle
    # total_arc = 2π - ширина рта
        arc = (2 * math.pi) - 2 * mouth_angle

    # Строим полигон: центр + точки по дуге
        points = [(px, py)]
        steps = 40
        for i in range(steps + 1):
            a = start + arc * (i / steps)
            points.append((px + math.cos(a) * r, py + math.sin(a) * r))

        pygame.draw.polygon(self.screen, color, points)

    # Глаз
        eye_offset_angle = base_angle + math.pi / 2   # перпендикуляр к движению
        eye_dist = r * 0.45
        eye_x = px + math.cos(eye_offset_angle) * eye_dist + d[0] * 2
        eye_y = py + math.sin(eye_offset_angle) * eye_dist + d[1] * 2
        pygame.draw.circle(self.screen, BLACK, (int(eye_x), int(eye_y)), 2)

    def draw_ghost(self, g, offset):
        gx = g.x*TILE_SIZE + offset[0] + TILE_SIZE//2
        gy = g.y*TILE_SIZE + HUD_HEIGHT + offset[1] + TILE_SIZE//2
        r = TILE_SIZE//2 - 2

        if g.eaten:
            color = (100, 100, 100)
        elif g.frightened:
            # мигание в конце
            if self.fright_timer < 2*FPS and (self.fright_timer // 10) % 2 == 0:
                color = FRIGHT_FLASH
            else:
                color = FRIGHT_BLUE
        else:
            color = g.color

        # тело призрака (полукруг + юбка)
        body_rect = pygame.Rect(gx - r, gy - r, r*2, r*2)
        pygame.draw.circle(self.screen, color, (gx, gy - 2), r, draw_top_right=True, draw_top_left=True)
        pygame.draw.rect(self.screen, color, (gx - r, gy - 2, r*2, r))

        # юбка
        wave = int(math.sin(g.anim * math.pi) * 3)
        for i in range(3):
            wx = gx - r + (i*2 + 1) * (r*2)//6
            wy = gy + r - 1 + (wave if i % 2 == 0 else -wave)
            pygame.draw.circle(self.screen, BLACK, (wx, wy), 3)

        if g.frightened:
            # глаза-крестики или рот
            pygame.draw.circle(self.screen, WHITE, (gx - 4, gy - 2), 2)
            pygame.draw.circle(self.screen, WHITE, (gx + 4, gy - 2), 2)
        else:
            # глаза
            ex1, ey1 = gx - 4, gy - 2
            ex2, ey2 = gx + 4, gy - 2
            pygame.draw.circle(self.screen, GHOST_EYE, (ex1, ey1), 4)
            pygame.draw.circle(self.screen, GHOST_EYE, (ex2, ey2), 4)
            # зрачки смотрят в сторону направления
            px = g.dir[0]*2
            py = g.dir[1]*2
            pygame.draw.circle(self.screen, GHOST_PUPIL, (ex1+px, ey1+py), 2)
            pygame.draw.circle(self.screen, GHOST_PUPIL, (ex2+px, ey2+py), 2)

    def draw_hud(self):
        # верхняя панель
        pygame.draw.rect(self.screen, (10, 10, 30), (0, 0, WIDTH, HUD_HEIGHT))
        pygame.draw.line(self.screen, BLUE, (0, HUD_HEIGHT-2), (WIDTH, HUD_HEIGHT-2), 2)

        score_surf = self.font_med.render(f"SCORE {self.score}", True, WHITE)
        self.screen.blit(score_surf, (10, 8))

        high_surf = self.font_small.render(f"HIGH {self.high_score}", True, YELLOW)
        self.screen.blit(high_surf, (10, 32))

        # жизни
        for i in range(self.lives):
            lx = WIDTH - 30 - i*25
            ly = 22
            pygame.draw.circle(self.screen, YELLOW, (lx, ly), 8)
            pygame.draw.polygon(self.screen, (10, 10, 30),
                                [(lx, ly), (lx+10, ly-5), (lx+10, ly+5)])

        # уровень
        lvl_surf = self.font_small.render(f"LEVEL {self.level}", True, CYAN)
        self.screen.blit(lvl_surf, (WIDTH//2 - lvl_surf.get_width()//2, 8))

        # режим
        mode_txt = f"MODE: {self.mode.upper()}"
        if self.fright_timer > 0:
            mode_txt = f"FRIGHT {self.fright_timer//FPS}"
        m_surf = self.font_small.render(mode_txt, True, ORANGE)
        self.screen.blit(m_surf, (WIDTH//2 - m_surf.get_width()//2, 30))

        # комбо
        if self.combo > 1:
            c_surf = self.font_med.render(f"COMBO x{self.combo}", True, PINK)
            self.screen.blit(c_surf, (WIDTH//2 - c_surf.get_width()//2, HUD_HEIGHT + 4))

        # точки
        p_surf = self.font_small.render(f"PELLETS {self.pellets_left}", True, PELLET_COLOR)
        self.screen.blit(p_surf, (WIDTH - p_surf.get_width() - 10, 8))

        # подсказка
        hint = self.font_small.render("WASD/Arrows  H:Help  M:Map  Tab:Skin  Space:Pause",
                                       True, (120, 120, 150))
        self.screen.blit(hint, (10, HEIGHT - 20))

    def draw_minimap(self):
        mw = 100
        mh = int(mw * ROWS / COLS)
        mx = WIDTH - mw - 8
        my = HEIGHT - mh - 26
        s = pygame.Surface((mw, mh), pygame.SRCALPHA)
        s.fill((0, 0, 0, 160))
        sx = mw / COLS
        sy = mh / ROWS
        for r in range(ROWS):
            for c in range(COLS):
                if self.grid[r][c] == 1:
                    pygame.draw.rect(s, (80, 80, 200, 200),
                                     (c*sx, r*sy, sx, sy))
        # призраки
        for g in self.ghosts:
            col = CYAN if g.frightened else g.color
            pygame.draw.circle(s, col, (int(g.x*sx), int(g.y*sy)), 2)
        # пакман
        pygame.draw.circle(s, YELLOW, (int(self.pacman.x*sx), int(self.pacman.y*sy)), 2)
        self.screen.blit(s, (mx, my))
        pygame.draw.rect(self.screen, WHITE, (mx, my, mw, mh), 1)

    def draw_centered(self, text, color, font, dy=0):
        surf = font.render(text, True, color)
        rect = surf.get_rect(center=(WIDTH//2, HEIGHT//2 + dy))
        self.screen.blit(surf, rect)

    def draw_help(self):
        s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        s.fill((0, 0, 0, 200))
        self.screen.blit(s, (0, 0))
        lines = [
            ("УПРАВЛЕНИЕ", YELLOW),
            ("WASD / Стрелки - движение", WHITE),
            ("SPACE - пауза", WHITE),
            ("R - рестарт", WHITE),
            ("M - мини-карта вкл/выкл", WHITE),
            ("TAB - сменить скин", WHITE),
            ("P - сохранить рекорд", WHITE),
            ("H / F1 - закрыть помощь", WHITE),
            ("", WHITE),
            ("ПРАВИЛА", YELLOW),
            ("Точки = +10 очков", PELLET_COLOR),
            ("Энергайзеры = +50, пугают призраков", POWER_COLOR),
            ("Съеденный в испуге призрак = 200 x комбо", CYAN),
            ("Фрукты = +100", RED),
            ("Соберите все точки, чтобы пройти уровень", WHITE),
            ("", WHITE),
            ("Скины: " + self.skins[self.skin]["name"], ORANGE),
        ]
        y = 80
        for text, color in lines:
            s = self.font_small.render(text, True, color)
            self.screen.blit(s, (60, y))
            y += 24

    # -------- Главный цикл --------
    def run(self):
        self.sound.play('start')
        while True:
            self.handle_input()
            self.update()
            self.draw()
            self.clock.tick(FPS)


if __name__ == "__main__":
    Game().run()
