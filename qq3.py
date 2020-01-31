#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
This is sample of how you can implement a tile-based game, not unlike
the RPG games known from consoles, in pygame. It's not a playable game,
but it can be turned into one. Care has been taken to comment it clearly,
so that you can use it easily as a starting point for your game.

The program reads a level definition from a "level.map" file, and uses the
graphics referenced for that file to display a tiled map on the screen and
let you move an animated player character around it.

Note that a lot of additional work is needed to turn it into an actual game.

@copyright: 2008, 2009 Radomir Dopieralski <qq@sheep.art.pl>
@license: BSD, see COPYING for details

"""

import configparser

import pygame
import pygame.locals as pg

# Motion offsets for particular directions
#     N  E  S   W
DX = [0, 1, 0, -1]
DY = [-1, 0, 1, 0]

# Dimensions of the map tiles
MAP_TILE_WIDTH, MAP_TILE_HEIGHT = 24, 16
FPS = 15

class TileCache(object):
    """Load the tilesets lazily into global cache"""

    def __init__(self,  width=32, height=None):
        self.width = width
        self.height = height or width
        self.cache = {}

    def __getitem__(self, filename):
        """Return a table of tiles, load it from disk if needed."""

        key = (filename, self.width, self.height)
        try:
            return self.cache[key]
        except KeyError:
            tile_table = self._load_tile_table(filename, self.width,
                                               self.height)
            self.cache[key] = tile_table
            return tile_table

    def _load_tile_table(self, filename, width, height):
        """Load an image and split it into tiles."""

        image = pygame.image.load(filename).convert()
        image_width, image_height = image.get_size()
        tile_table = []
        for tile_x in range(0, image_width // width):
            line = []
            tile_table.append(line)
            for tile_y in range(0, image_height // height):
                rect = (tile_x*width, tile_y*height, width, height)
                line.append(image.subsurface(rect))
        return tile_table


class SortedUpdates(pygame.sprite.RenderUpdates):
    """A sprite group that sorts them by depth."""

    def sprites(self):
        """The list of sprites in the group, sorted by depth."""

        return sorted(list(self.spritedict.keys()), key=lambda sprite: sprite.depth)


class Shadow(pygame.sprite.Sprite):
    """Sprite for shadows."""

    def __init__(self, owner):
        pygame.sprite.Sprite.__init__(self)
        self.image = SPRITE_CACHE["shadow.png"][0][0]
        self.image.set_alpha(64)
        self.rect = self.image.get_rect()
        self.owner = owner

    def update(self, *args):
        """Make the shadow follow its owner."""

        self.rect.midbottom = self.owner.rect.midbottom


class Sprite(pygame.sprite.Sprite):
    """Sprite for animated items and base class for Player."""

    is_player = False

    def __init__(self, pos=(0, 0), frames=None):
        super(Sprite, self).__init__()
        if frames:
            self.frames = frames
        self.image = self.frames[0][0]
        self.rect = self.image.get_rect()
        self.animation = self.stand_animation()
        self.pos = pos

    def _get_pos(self):
        """Check the current position of the sprite on the map."""

        return ((self.rect.midbottom[0] - 12) // 24,
                (self.rect.midbottom[1] - 16) // 16)

    def _set_pos(self, pos):
        """Set the position and depth of the sprite on the map."""

        self.rect.midbottom = pos[0]*24+12, pos[1]*16+16
        self.depth = self.rect.midbottom[1]

    pos = property(_get_pos, _set_pos)

    def move(self, dx, dy):
        """Change the position of the sprite on screen."""

        self.rect.move_ip(dx, dy)
        self.depth = self.rect.midbottom[1]

    def stand_animation(self):
        """The default animation."""

        while True:
            # Change to next frame every two ticks
            for frame in self.frames[0]:
                self.image = frame
                yield None
                yield None

    def update(self, *args):
        """Run the current animation."""

        next(self.animation)


class Player(Sprite):
    """ Display and animate the player character."""

    is_player = True

    def __init__(self, pos=(1, 1)):
        self.frames = SPRITE_CACHE["player.png"]
        Sprite.__init__(self, pos)
        self.direction = 2
        self.animation = None
        self.image = self.frames[self.direction][0]

    def walk_animation(self, multiplier):
        """Animation for the player walking."""

        # This animation is hardcoded for 4 frames and 16x24 map tiles
        for frame in range(4):
            self.image = self.frames[self.direction][frame]
            yield None
            self.move(3*multiplier*DX[self.direction], 2*multiplier*DY[self.direction])
            yield None
            self.move(3*multiplier*DX[self.direction], 2*multiplier*DY[self.direction])

    def update(self, *args):
        """Run the current animation or just stand there if no animation set."""

        if self.animation is None:
            self.image = self.frames[self.direction][0]
        else:
            try:
                next(self.animation)
            except StopIteration:
                self.animation = None

class Level(object):
    """Load and store the map of the level, together with all the items."""

    def __init__(self, filename="level.map"):
        self.tileset = ''
        self.map = []
        self.items = {}
        self.key = {}
        self.width = 0
        self.height = 0
        self.load_file(filename)

    def load_file(self, filename="level.map"):
        """Load the level from specified file."""

        parser = configparser.ConfigParser()
        parser.read(filename)
        self.tileset = parser.get("level", "tileset")
        self.map = parser.get("level", "map").split("\n")
        for section in parser.sections():
            if len(section) == 1:
                desc = dict(parser.items(section))
                self.key[section] = desc
        self.width = len(self.map[0])
        self.height = len(self.map)
        for y, line in enumerate(self.map):
            for x, c in enumerate(line):
                if not self.is_wall(x, y) and 'sprite' in self.key[c]:
                    self.items[(x, y)] = self.key[c]

    def render(self):
        """Draw the level on the surface."""

        wall = self.is_wall
        tiles = MAP_CACHE[self.tileset]
        image = pygame.Surface((self.width*MAP_TILE_WIDTH, self.height*MAP_TILE_HEIGHT))
        overlays = {}
        for map_y, line in enumerate(self.map):
            for map_x, c in enumerate(line):
                if wall(map_x, map_y):
                    # Draw different tiles depending on neighbourhood
                    if not wall(map_x, map_y+1):
                        if wall(map_x+1, map_y) and wall(map_x-1, map_y):
                            tile = 1, 2
                        elif wall(map_x+1, map_y):
                            tile = 0, 2
                        elif wall(map_x-1, map_y):
                            tile = 2, 2
                        else:
                            tile = 3, 2
                    else:
                        if wall(map_x+1, map_y+1) and wall(map_x-1, map_y+1):
                            tile = 1, 1
                        elif wall(map_x+1, map_y+1):
                            tile = 0, 1
                        elif wall(map_x-1, map_y+1):
                            tile = 2, 1
                        else:
                            tile = 3, 1
                    # Add overlays if the wall may be obscuring something
                    if not wall(map_x, map_y-1):
                        if wall(map_x+1, map_y) and wall(map_x-1, map_y):
                            over = 1, 0
                        elif wall(map_x+1, map_y):
                            over = 0, 0
                        elif wall(map_x-1, map_y):
                            over = 2, 0
                        else:
                            over = 3, 0
                        overlays[(map_x, map_y)] = tiles[over[0]][over[1]]
                else:
                    try:
                        tile = self.key[c]['tile'].split(',')
                        tile = int(tile[0]), int(tile[1])
                    except (ValueError, KeyError):
                        # Default to ground tile
                        tile = 0, 3
                tile_image = tiles[tile[0]][tile[1]]
                image.blit(tile_image,
                           (map_x*MAP_TILE_WIDTH, map_y*MAP_TILE_HEIGHT))
        return image, overlays

    def get_tile(self, x, y):
        """Tell what's at the specified position of the map."""

        try:
            char = self.map[y][x]
        except IndexError:
            return {}
        try:
            return self.key[char]
        except KeyError:
            return {}

    def get_bool(self, x, y, name):
        """Tell if the specified flag is set for position on the map."""

        value = self.get_tile(x, y).get(name)
        return value in (True, 1, 'true', 'yes', 'True', 'Yes', '1', 'on', 'On')

    def is_wall(self, x, y):
        """Is there a wall?"""

        return self.get_bool(x, y, 'wall')

    def is_blocking(self, x, y):
        """Is this place blocking movement?"""

        if not 0 <= x < self.width or not 0 <= y < self.height:
            return True
        return self.get_bool(x, y, 'block')


class Game(object):
    """The main game object."""  

    def __init__(self):
        self.screen = pygame.display.get_surface()
        self.pressed_key = None
        self.game_over = False
        self.shadows = pygame.sprite.RenderUpdates()
        self.sprites = SortedUpdates()
        self.overlays = pygame.sprite.RenderUpdates()
        
        self.features = ["bush", "forward", "backward", "stop", "crate"]
        
        self.bushstuff = []
        self.interact = []
        self.potato = 499
        self.weight = False
        self.weightnum = 250
        self.maxcapacity = 500
        self.donation = 0
        self.needed = 1000
        self.deadline = 365 * FPS
        self.stoppedtime = 25 * FPS
        self.is_time_stopped = False
        
        self.save = []
        
        self.use_level(Level())        

    def use_level(self, level):
        """Set the level as the current one."""
        def around(pos, name):
            x, y = pos
            place = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
            thing = [name, place]
            if name == "bush":
                is_done = False
                timeleft = -1
                self.bushstuff.append([place, is_done, timeleft])
            self.interact.append(thing)        
    
        self.shadows = pygame.sprite.RenderUpdates()
        self.sprites = SortedUpdates()
        self.overlays = pygame.sprite.RenderUpdates()
        self.level = level
        # Populate the game with the level's objects
        for pos, tile in level.items.items():
            if tile['name'] in self.features:
                x, y = pos
                #self.interact.append([tile['name'], (x, y)])                
                around(pos, tile['name'])
                
            if tile.get("player") in ('true', '1', 'yes', 'on'):
                sprite = Player(pos)
                self.player = sprite
            else:
                sprite = Sprite(pos, SPRITE_CACHE[tile["sprite"]])
            self.sprites.add(sprite)
            self.shadows.add(Shadow(sprite))
        # Render the level map
        self.background, overlays = self.level.render()
        # Add the overlays for the level map
        for (x, y), image in overlays.items():
            overlay = pygame.sprite.Sprite(self.overlays)
            overlay.image = image
            overlay.rect = image.get_rect().move(x*24, y*16-16)

    def control(self):
        """Handle the controls of the game."""

        keys = pygame.key.get_pressed()

        def pressed(key):
            """Check if the specified key is pressed."""

            return self.pressed_key == key or keys[key]

        def walk(d, is_run):
            """Start walking in specified direction."""

            x, y = self.player.pos
            self.player.direction = d
            multiplier = 1
            if is_run is True:
                multiplier = 2
            if is_run is True and self.is_time_stopped is True:
                multiplier = 3
            if self.level.is_blocking(x+multiplier*DX[d], y+multiplier*DY[d]):
                multiplier = 1
            if not self.level.is_blocking(x+DX[d], y+DY[d]):
                self.player.animation = self.player.walk_animation(multiplier)
        
        def interact():
            def potato_affect(effect):
                time = 0
                if effect is True:
                    time = -5
                else:
                    time = 20
                for j in self.bushstuff:
                    if j[2] > 0:
                        print("The potato something", j[2], time, j[2] + time)                                                 
                        j[2] = j[2] + time * FPS
                        if j[2] <= 0:
                            self.potato += 200 + bonus    
                            j[1] = False
                            j[2] = -1   
                        if j[2] > 20:
                            j[1] = False
                            j[2] = -1
            """Interact with an object"""
            x, y = self.player.pos
            pos = x, y
            for i in self.interact:
                if pos in i[1] and i[0] == 'forward':
                    if self.potato >= 40:
                        pygame.mixer.music.stop()
                        music = pygame.mixer.Sound('rewind.wav')
                        music.play()                        
                        self.deadline -= 5 * FPS
                        self.potato -= 40         
                        potato_affect(True)
                if pos in i[1] and i[0] == 'stop' and self.is_time_stopped is False:
                    if self.potato >= 250:
                        pygame.mixer.music.stop()
                        music = pygame.mixer.Sound('stoptime.wav')
                        music.play()                           
                        self.is_time_stopped = True
                        self.potato -= 250                
                if pos in i[1] and i[0] == 'backward':
                    if self.potato >= 40:
                        pygame.mixer.music.stop()
                        music = pygame.mixer.Sound('rewind.wav')
                        music.play()                        
                        self.deadline += 15 * FPS
                        self.potato -= 40
                        potato_affect(False)
                if pos in i[1] and self.potato >= 0 and self.maxcapacity > self.potato and i[0] == 'bush':
                    bonus = 0
                    if self.is_time_stopped is True:
                        bonus = 50
                    for j in self.bushstuff:
                        if pos in j[0]:
                            bush = self.bushstuff.index(j)
                                      
                    if self.bushstuff[bush][1] is False and self.bushstuff[bush][2] < 0:
                        self.bushstuff[bush][2] = 20 * FPS
                        myfont = pygame.font.SysFont("monospace", 16)
                        scoretext = myfont.render("POTATO PLANTED!", 1, (124,252,0))
                        self.screen.blit(scoretext, (5, 330))                         
                    elif self.bushstuff[bush][1] is True and self.bushstuff[bush][2] == 0:
                        self.potato += 50 + bonus    
                        self.bushstuff[bush][1] = False
                        self.bushstuff[bush][2] = -1
                    else:
                        myfont = pygame.font.SysFont("monospace", 16)
                        scoretext = myfont.render("TIME LEFT TO GROW: {0}".format(self.bushstuff[bush][2] // FPS), 1, (255,255,102))
                        self.screen.blit(scoretext, (5, 330))                        
                
                if pos in i[1] and self.potato > 0  and i[0] == 'house':
                    coef = 0
                    maximum = 500
                    while maximum != 0:
                        if self.potato >= maximum:
                            coef = maximum
                            break
                        else:
                            maximum = maximum // 2
                    self.potato -= coef
                    self.donation += coef
                        
        
        keys = pygame.key.get_pressed()
        
        if (keys[pg.K_UP] and keys[pg.K_LSHIFT]) or keys[pg.K_UP]:
            is_run = False
            if (keys[pg.K_LSHIFT] and self.weight == False) or (keys[pg.K_LSHIFT] and self.is_time_stopped is True):
                is_run = True
            walk(0, is_run)
        elif (keys[pg.K_DOWN] and keys[pg.K_LSHIFT]) or keys[pg.K_DOWN]:
            is_run = False
            if (keys[pg.K_LSHIFT] and self.weight == False) or (keys[pg.K_LSHIFT] and self.is_time_stopped is True):
                is_run = True
            walk(2, is_run)
        elif (keys[pg.K_LEFT] and keys[pg.K_LSHIFT]) or keys[pg.K_LEFT]:
            is_run = False
            if (keys[pg.K_LSHIFT] and self.weight == False) or (keys[pg.K_LSHIFT] and self.is_time_stopped is True):
                is_run = True
            walk(3, is_run)
        elif (keys[pg.K_RIGHT] and keys[pg.K_LSHIFT]) or keys[pg.K_RIGHT]:
            is_run = False
            if (keys[pg.K_LSHIFT] and self.weight == False) or (keys[pg.K_LSHIFT] and self.is_time_stopped is True):
                is_run = True
            walk(1, is_run)
        elif keys[pg.K_e]:
            interact()
        self.pressed_key = None        
        

    def main(self):
        def start_game():
            self.screen.fill((0, 0, 0))
            start_img = pygame.image.load('start.png')
            start_img_rect = start_img.get_rect()
            start_img_rect.center = (MAP_TILE_WIDTH * 35 / 2, MAP_TILE_HEIGHT * 23 / 2)
            self.screen.blit(start_img, start_img_rect)
            exit = False
            while True:
                for event in pygame.event.get():
                    if event.type == pygame.KEYDOWN:
                        exit = True
                if exit == True:
                    break
                pygame.display.update()
                
        def game_over():
            self.screen.fill((0, 0, 0))
            end_img = pygame.image.load('end.png')
            end_img_rect = end_img.get_rect()
            end_img_rect.center = (MAP_TILE_WIDTH * 35 / 2, MAP_TILE_HEIGHT * 23 / 2)
            self.screen.blit(end_img, end_img_rect)
            exit = False
            while True:
                for event in pygame.event.get():
                    if event.type == pygame.KEYDOWN:
                        exit = True
                        pygame.display.quit()
                        pygame.quit()
                if exit == True:
                    break
                pygame.display.update() 
        
        def timestop():             
            scoretext = myfont.render("TIME STOPPED", 1, (0,0,255))                
            self.screen.blit(scoretext, (5, 290)) 
            scoretext = myfont.render("SECONDS LEFT: {0}".format(self.stoppedtime // FPS), 1, (0,0,255))
            self.screen.blit(scoretext, (5, 310)) 
            if self.stoppedtime == 0:
                self.is_time_stopped = False
                self.stoppedtime = 10 * FPS
            else:
                self.stoppedtime -= 1            
        
        def display():
            scoretext = myfont.render("POTATOES: {0}".format(self.potato), 1, (255,255,255))
            self.screen.blit(scoretext, (5, 210)) 
            
            scoretext = myfont.render("TIME LEFT BEFORE AFRICA DIES: {0}".format(self.deadline // FPS), 1, (255,255,255))
            self.screen.blit(scoretext, (5, 230))
            
            scoretext = myfont.render("POTATOES DONATED TO AFRICA: {0}".format(self.donation), 1, (255,255,255))
            self.screen.blit(scoretext, (5, 250)) 
            
            scoretext = myfont.render("POTATOES NEEDED FOR GOAL: {0}".format(self.needed), 1, (255,255,255))
            self.screen.blit(scoretext, (5, 270))            
        
        def potatogrow():
            for j in self.bushstuff:
                if j[1] is False and j[2] > 0:
                    j[2] -= 1
                if j[2] == 0 and j[1] is not True:
                    j[1] = True
        
        """Run the main loop."""
        start_game()

        clock = pygame.time.Clock()
        # Draw the whole screen initially
        self.screen.blit(self.background, (0, 0))
        self.overlays.draw(self.screen)
        pygame.display.flip()
        # The main game loop
            
        pygame.mixer.music.stop()
        music = pygame.mixer.Sound('music.wav')
        music.play()                           
        while not self.game_over:
            
            myfont = pygame.font.SysFont("monospace", 16)
            self.screen.fill((0,0,0))
            
            self.screen.blit(self.background, (0, 0))
            
            if self.is_time_stopped is True:
                timestop()
                    
            display()      
            
            if self.deadline != 0 and self.is_time_stopped is False:
                self.deadline -= 1
            if self.potato >= self.weightnum:
                self.weight = True
            else:
                self.weight = False
            
            if self.is_time_stopped is False:
                potatogrow()
            
            # Don't clear shadows and overlays, only sprites.
            self.sprites.clear(self.screen, self.background)
            self.sprites.update()
            # If the player's animation is finished, check for keypresses
            if self.player.animation is None:
                self.control()
                self.player.update()
            self.shadows.update()
            # Don't add shadows to dirty rectangles, as they already fit inside
            # sprite rectangles.
            self.shadows.draw(self.screen)
            dirty = self.sprites.draw(self.screen)
            # Don't add ovelays to dirty rectangles, only the places where
            # sprites are need to be updated, and those are already dirty.
            self.overlays.draw(self.screen)
            # Update the dirty areas of the screen
            pygame.display.update(dirty)
            # Wait for one tick of the game clock
            clock.tick(15)
            # Process pygame events
            for event in pygame.event.get():
                if self.deadline == 0 and self.needed != 0:
                    self.game_over = True
                if event.type == pg.QUIT:
                    self.game_over = True
                elif event.type == pg.KEYDOWN:
                    self.pressed_key = event.key
                    
            pygame.display.flip()
        game_over()               
        
                    
            
#I didnt enclude a start or end screen picure
#Just rename the picture start.png and gameover.png
#I encluded some music in too when u die



           
if __name__ == "__main__":
    SPRITE_CACHE = TileCache()
    MAP_CACHE = TileCache(MAP_TILE_WIDTH, MAP_TILE_HEIGHT)
    TILE_CACHE = TileCache(32, 32)
    pygame.init()
    pygame.display.set_mode((MAP_TILE_WIDTH * 35, MAP_TILE_HEIGHT * 23))
    Game().main()
