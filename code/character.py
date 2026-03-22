"""
character.py - Character classes for the game

Students create 4 unique character classes, each with:
- Different stats (hp, attack, defense, speed)
- Unique special ability
- Character sprite image

Author: Nicholas Waller
Date: 1/26/2026
Lab: Lab 2 - Character Classes
"""

import pygame
from settings import *

class Character(pygame.sprite.Sprite):
    """Base Character class - all characters inherit from this"""
    
    def __init__(self, pos, groups, obstacle_sprites):
        super().__init__(groups)

        # Stats (override in subclasses)
        self.character_name = "Unknown"
        self.max_hp = 100
        self.attack = 10
        self.defense = 5
        self.speed = 5
        
        # DO NOT EDIT
        self.image = pygame.Surface((64, 64))
        self.image.fill((255, 0, 255))  # Magenta placeholder
        self.rect = self.image.get_rect(topleft=pos)
        self.hitbox = self.rect.inflate(0, -26)
        
        # Movement
        self.direction = pygame.math.Vector2()
        self.obstacle_sprites = obstacle_sprites
        
    def input(self):
        """Handle player input"""
        keys = pygame.key.get_pressed()

        if keys[pygame.K_UP]:
            self.direction.y = -1
        elif keys[pygame.K_DOWN]:
            self.direction.y = 1
        else:
            self.direction.y = 0

        if keys[pygame.K_RIGHT]:
            self.direction.x = 1
        elif keys[pygame.K_LEFT]:
            self.direction.x = -1
        else:
            self.direction.x = 0
    
    def move(self, speed):
        """Move the character"""
        if self.direction.magnitude() != 0:
            self.direction = self.direction.normalize()

        self.hitbox.x += self.direction.x * speed
        self.collision('horizontal')
        self.hitbox.y += self.direction.y * speed
        self.collision('vertical')
        self.rect.center = self.hitbox.center
    
    def collision(self, direction):
        """Handle collision with obstacles"""
        if direction == 'horizontal':
            for sprite in self.obstacle_sprites:
                if sprite.hitbox.colliderect(self.hitbox):
                    if self.direction.x > 0:  # moving right
                        self.hitbox.right = sprite.hitbox.left
                    if self.direction.x < 0:  # moving left
                        self.hitbox.left = sprite.hitbox.right

        if direction == 'vertical':
            for sprite in self.obstacle_sprites:
                if sprite.hitbox.colliderect(self.hitbox):
                    if self.direction.y > 0:  # moving down
                        self.hitbox.bottom = sprite.hitbox.top
                    if self.direction.y < 0:  # moving up
                        self.hitbox.top = sprite.hitbox.bottom
    
    def update(self):
        """Update character each frame"""
        self.input()
        self.move(self.speed)

        
    def special_ability(self):
        """Special ability - override in subclasses"""
        pass
    
    @staticmethod
    def get_display_name():
        """Return character name for display"""
        return "Unknown"
    
    @staticmethod
    def get_description():
        """Return character description"""
        return 
    
    @staticmethod
    def get_preview_image():
        """Return path to character preview image"""
        return '../graphics/test/player.png'


# ============================================
# IMPLEMENT THESE 4 CLASSES
# ============================================

class Pitcher(Character):
    """
    TODO: Implement class
    
    """
    def __init__(self, character_name, avg_modifier, slg_modifier, stamina):

        
        # TODO: Set character image
        #self.image = pygame.image.load('../graphics/test/pitcher.png').convert_alpha()
        #self.rect = self.image.get_rect(topleft=pos)
        #self.hitbox = self.rect.inflate(0, -26)
        
        # TODO: Set stats
        self._character_name = character_name
        self.__avg_modifier = avg_modifier  
        self.__slg_modifier = slg_modifier
        self.__stamina = stamina

    def reduce_stamina(self, damage):
        self.damage = damage
        self.__stamina -= damage

        if self.__stamina < 0:
            self.__stamina = 0
        return damage
    
    def is_alive(self):
        if self.__stamina <= 0:
            return False
        if self.stamina > 0:
            return True

    def heal(self, amount):
        if self.stamina + amount > 100:
            self.stamina = 100
        else:
            self.stamina += amount

        return amount

    
    def special_ability(self, hot_streak): #boost pitchers stats temporarily
        # TODO: Implement special ability
        self.avg_modifier += hot_streak 
        self.slg_modifier += hot_streak
        return 
    
    # ### TODO: Uncomment and implement these
    @staticmethod
    def get_display_name():
        return Pitcher.character_name
    
    @staticmethod
    def get_description():
         return "An electric young pitcher with high velocity and command"
    
    @staticmethod
    def get_preview_image():
  
        return "../graphics/game characters/pitcher.png"


class Catcher(Character):
    def __init__(self, character_name, ops, average, slugging):
        #super().__init__(pos, groups, obstacle_sprites)

        #self.image = pygame.image.load('../graphics/test/fielder.png').convert_alpha()
        #self.rect = self.image.get_rect(topleft=pos)
        #self.hitbox = self.rect.inflate(0, -26)

        self._character_name = character_name # I dont want player changing the athlets names
        self.__ops = ops
        self.__average = average
        self.__slugging = slugging

    def special_ability(self, steady_hand): #boost pitchers stats temporarily
        self.avg_modifier += steady_hand 
        self.slg_modifier += steady_hand
        return  steady_hand

    @staticmethod
    def get_display_name():
        return Catcher.character_name

    @staticmethod
    def get_description():
        return "Commands the defense and provides power at the plate"
    
    @staticmethod
    def get_preview_image():
  
        return "../graphics/game characters/hitter.png"

class Coach(Character):
    def __init__(self, character_name, ops_plus, average_plus, slugging_plus):
        #super().__init__(pos, groups, obstacle_sprites)
        
        # TODO: Set character image
        #self.image = pygame.image.load('../graphics/test/coach.png').convert_alpha()
        #self.rect = self.image.get_rect(topleft=pos)
        #self.hitbox = self.rect.inflate(0, -26)
        
        # TODO: Set stats
        self._character_name = character_name
        self.__ops_plus = ops_plus
        self.__average_plus = average_plus
        self.__slugging_plus = slugging_plus
    
    # ### TODO: Uncomment and implement these
    def motivational_speech(self, pitcher):
        pitcher.stamina += 40
        return
    
    def apply_coaching(self,hitter):
        hitter.ops += self.ops_plus
        hitter.average += self.average_plus
        hitter.slugging += self.slugging_plus
        return
    
    @staticmethod
    def get_display_name():
         return Coach.character_name
    
    @staticmethod
    def get_description():
       return "improves the stats of your batter"
    
    @staticmethod
    def get_preview_image():
        return "../graphics/game characters/coach.png"

class Second_baseman(Character):
    """
    TODO: Implement class
    
    """
    def __init__(self, character_name, ops, slugging, average, pos, groups, obstacle_sprites):
        super().__init__(pos, groups, obstacle_sprites)
        
        # TODO: Set character image
        self.image = pygame.image.load('../graphics/test/player.png').convert_alpha()
        self.rect = self.image.get_rect(topleft=pos)
        self.hitbox = self.rect.inflate(0, -26)
        
        # TODO: Set stats
        self.character_name = character_name
        self.ops = ops
        self.average = average
        self.slugging = slugging
    

    def special_ability(self, player, hype_man): #boost stamina for entire team
        player.stamina += hype_man
        return

    @staticmethod
    def get_display_name():
         return Second_baseman.character_name
    
    @staticmethod
    def get_description():
         return "an integral player for your defense as well as a consistent contact hitter on offense"
    
    @staticmethod
    def get_preview_image():
        return "../graphics/game characters/second_baseman.png"

# ============================================
# CHARACTER REGISTRY (Auto-discovery)
# ============================================

def get_all_character_classes():
    """
    Automatically discover all character classes
    Returns list of character classes (not instances)
    """
    # Get all subclasses of Character
    character_classes = []
    
    for cls in Character.__subclasses__():
        # Skip the base Character class
        if cls.__name__ != 'Character':
            character_classes.append(cls)
    
    return character_classes
