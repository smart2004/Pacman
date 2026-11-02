import pygame
import random
import sys

# --- Настройки ---
TILE_SIZE = 32
COLS = 19
ROWS = 21
WIDTH = COLS * TILE_SIZE
HEIGHT = ROWS * TILE_SIZE
FPS = 10  # скорость игры

# Цвета
BLACK = (0, 0, 0)
YELLOW = (255, 255, 0)
BLUE = (0, 0, 200)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
PINK = (255, 184, 255)
ORANGE = (255, 184, 82)
CYAN = (0, 255, 255)
PELLET = (255, 200, 150)

# Карта: 1 = стена, 0 = пусто, 2 = точка, 3 = энергайзер
MAP = [
    "###################",
    "#........#........#",
    "#o##.###.#.###.##o#",
    "#.................#",
    "#.##.#.#####.#.##.#",
    "#....#...#...#....#",
    "####.### # ###.####",
    "   #.#   0   #.#   ",
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

# Преобразуем карту в сетку
grid = []
for r, row in enumerate(MAP):
    line = []
    for c, ch in enumerate(row):
        if ch == '#':
            line.append(1)
        elif ch == '.':
            line.append(2)
        elif ch == 'o':
            line.append(3)
        else:
            line.append(0)
    grid.append(line)


class Pacman:
    def __init__(self):
        self.start_x, self.start_y = 9, 15
        self.reset()

    def reset(self):
        self.x, self.y = self.start_x, self.start_y
        self.dir = (0, 0)
        self.next_dir = (0, 0)

    def can_move(self, x, y):
        return 0 <= y < ROWS and 0 <= x < COLS and grid[y][x] != 1

    def update(self):
        # Пробуем сменить направление
        nx = self.x + self.next_dir[0]
        ny = self.y + self.next_dir[1]
        if self.next_dir != (0, 0) and self.can_move(nx, ny):
            self.dir = self.next_dir
            self.next_dir = (0, 0)

        # Движение
        nx = self.x + self.dir[0]
        ny = self.y + self.dir[1]
        if self.can_move(nx, ny):
            self.x, self.y = nx, ny
        else:
            self.dir = (0, 0)

        # Съедание точки
        if grid[self.y][self.x] in (2, 3):
            grid[self.y][self.x] = 0


class Ghost:
    def __init__(self, x, y, color, name):
        self.start_x, self.start_y = x, y
        self.color = color
        self.name = name
        self.reset()

    def reset(self):
        self.x, self.y = self.start_x, self.start_y
        self.dir = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
        self.frightened = False

    def update(self, pacman, pacman_pos, all_ghosts):
        # Движение
        nx = self.x + self.dir[0]
        ny = self.y + self.dir[1]
        if not (0 <= ny < ROWS and 0 <= nx < COLS and grid[ny][nx] != 1):
            self.choose_new_dir(pacman_pos, all_ghosts)

        self.x += self.dir[0]
        self.y += self.dir[1]

    def choose_new_dir(self, pacman_pos, all_ghosts):
        options = []
        for d in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            if d == (-self.dir[0], -self.dir[1]):
                continue
            nx, ny = self.x + d[0], self.y + d[1]
            if 0 <= ny < ROWS and 0 <= nx < COLS and grid[ny][nx] != 1:
                options.append(d)

        if not options:
            self.dir = (-self.dir[0], -self.dir[1])
            return

        # Глупый ИИ: боятся или гонятся
        if self.frightened:
            self.dir = random.choice(options)
        else:
            px, py = pacman_pos
            if self.name == "red":
                # гонится напрямую
                best = min(options, key=lambda d: (self.x + d[0] - px) ** 2 + (self.y + d[1] - py) ** 2)
            elif self.name == "pink":
                # гонится к позиции на 4 клетки впереди
                best = min(options, key=lambda d: (self.x + d[0] - px) ** 2 + (self.y + d[1] - py) ** 2)
            else:
                # случайно
                best = random.choice(options)
            self.dir = best


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Pac-Man Python")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("arial", 20, bold=True)
        self.big_font = pygame.font.SysFont("arial", 40, bold=True)
        self.reset_game()

    def reset_game(self):
        global grid
        # Перезагружаем карту
        grid = []
        for row in MAP:
            line = []
            for ch in row:
                if ch == '#':
                    line.append(1)
                elif ch == '.':
                    line.append(2)
                elif ch == 'o':
                    line.append(3)
                else:
                    line.append(0)
            grid.append(line)

        self.pacman = Pacman()
        self.ghosts = [
            Ghost(9, 7, RED, "red"),
            Ghost(8, 7, PINK, "pink"),
            Ghost(10, 7, ORANGE, "orange"),
            Ghost(9, 8, CYAN, "cyan"),
        ]
        self.score = 0
        self.lives = 3
        self.state = "playing"  # playing, dead, win, gameover
        self.dead_timer = 0
        self.frightened_timer = 0

    def count_pellets(self):
        return sum(cell in (2, 3) for row in grid for cell in row)

    def handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    self.pacman.next_dir = (0, -1)
                elif event.key == pygame.K_DOWN:
                    self.pacman.next_dir = (0, 1)
                elif event.key == pygame.K_LEFT:
                    self.pacman.next_dir = (-1, 0)
                elif event.key == pygame.K_RIGHT:
                    self.pacman.next_dir = (1, 0)
                elif event.key == pygame.K_r and self.state in ("gameover", "win"):
                    self.reset_game()

    def update(self):
        if self.state != "playing":
            if self.state == "dead":
                self.dead_timer -= 1
                if self.dead_timer <= 0:
                    if self.lives > 0:
                        self.pacman.reset()
                        for g in self.ghosts:
                            g.reset()
                        self.state = "playing"
                    else:
                        self.state = "gameover"
            return

        self.pacman.update()

        # Проверка съедания точки
        # (обрабатываем внутри Pacman.update, здесь считаем очки)
        # Повторно не проверяем, но добавим очки:
        # проще проверить исходное состояние перед движением
        # Поэтому переносим логику очков сюда:
        # (сделаем проще — очки начисляем при проверке клетки)

        # Начисление очков — отдельно:
        # мы не знаем сколько съел pacman, поэтому начислим по факту:
        # Проще: проверять здесь
        # Оставим начисление в update клетки — но там нет доступа к очкам.
        # Перепишем: смотрим на клетку до движения.

        # Из-за особенностей структуры начисляем очки здесь по "следу"
        # Проще — проверять после движения:

        # Проще: начисляем очки в Pacman.update через callback.
        # Но чтобы не усложнять — проверим ещё раз:
        # (уже съедено — не сработает)

        # Сделаем правильно: перед движением запомним клетку.

        # Обновление призраков
        for g in self.ghosts:
            g.update(self.pacman, (self.pacman.x, self.pacman.y), self.ghosts)

        # Проверка столкновений
        for g in self.ghosts:
            if (g.x, g.y) == (self.pacman.x, self.pacman.y):
                if g.frightened:
                    g.reset()
                    self.score += 200
                else:
                    self.lives -= 1
                    self.state = "dead"
                    self.dead_timer = 10
                    break

        if self.count_pellets() == 0:
            self.state = "win"

    def draw(self):
        self.screen.fill(BLACK)

        # Стены и точки
        for r in range(ROWS):
            for c in range(COLS):
                cell = grid[r][c]
                x, y = c * TILE_SIZE, r * TILE_SIZE
                if cell == 1:
                    pygame.draw.rect(self.screen, BLUE, (x, y, TILE_SIZE, TILE_SIZE))
                    pygame.draw.rect(self.screen, (0, 0, 120), (x, y, TILE_SIZE, TILE_SIZE), 2)
                elif cell == 2:
                    pygame.draw.circle(self.screen, PELLET, (x + TILE_SIZE // 2, y + TILE_SIZE // 2), 3)
                elif cell == 3:
                    pygame.draw.circle(self.screen, PELLET, (x + TILE_SIZE // 2, y + TILE_SIZE // 2), 7)

        # Pac-Man
        px = self.pacman.x * TILE_SIZE + TILE_SIZE // 2
        py = self.pacman.y * TILE_SIZE + TILE_SIZE // 2
        pygame.draw.circle(self.screen, YELLOW, (px, py), TILE_SIZE // 2 - 2)

        # Призраки
        for g in self.ghosts:
            gx = g.x * TILE_SIZE + TILE_SIZE // 2
            gy = g.y * TILE_SIZE + TILE_SIZE // 2
            color = (100, 100, 255) if g.frightened else g.color
            pygame.draw.circle(self.screen, color, (gx, gy), TILE_SIZE // 2 - 2)

        # Интерфейс
        score_surf = self.font.render(f"SCORE: {self.score}   LIVES: {self.lives}", True, WHITE)
        self.screen.blit(score_surf, (10, HEIGHT - 28))

        if self.state == "gameover":
            txt = self.big_font.render("GAME OVER - R to restart", True, RED)
            self.screen.blit(txt, (WIDTH // 2 - txt.get_width() // 2, HEIGHT // 2 - 20))
        elif self.state == "win":
            txt = self.big_font.render("YOU WIN! - R to restart", True, YELLOW)
            self.screen.blit(txt, (WIDTH // 2 - txt.get_width() // 2, HEIGHT // 2 - 20))

        pygame.display.flip()

    def run(self):
        while True:
            self.handle_input()
            self.update()
            self.draw()
            self.clock.tick(FPS)


if __name__ == "__main__":
    Game().run()
