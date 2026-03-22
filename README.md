[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/UQTafpTI)
# Lab 2: Character System

## Purpose
The purpose of Lab 2 is to:
1. Implement your first Python classes using Object-Oriented Programming (OOP)
2. Create a character system for your game with inheritance
3. Build character classes based on your Lab 1 design
4. Generate character sprites using AI
5. Write tests to verify your code works correctly

This is your first real coding assignment! 

---

## Part 1: Character Base Class (1-2 hours)

There is a file called `code/character.py` that implements the base `Character` class. You will build subclasses which inherit from `Character`. Here are the attributes and methods you will override (DO NOT touch anything else):

**Attributes (in `__init__`):**
- `character_name` (string): Character's name
- `hp` (int): Current hit points
- `max_hp` (int): Maximum hit points
- `attack` (int): Attack power
- `defense` (int): Defense value
- `speed` (int): Speed/agility value

**Methods:**
- `__init__(self, name, hp, attack, defense, speed)`: Constructor
- `special_ability(self)`: The special ability of your character
- `get_display_name()`: Return character name for display
- `get_description()`: Return character description
- `get_preview_image()`: Return path to character preview image

**Methods for you to implement:**
- `take_damage(self, damage)`: Reduce HP by damage (accounting for defense)
- `heal(self, amount)`: Restore HP (cannot exceed max_hp)
- `is_alive(self)`: Return True if hp > 0

### Requirements
1. Understand what these methods are doing.
2. Edit the constructor so that a **valid** object is returned. It is up to you to decide how to do this.
3. To validate the object you must use at least one private and one protected method. Justify your choices.
4. Implement the methods `take_damage`, `heal`, and `is_alive`.
5. Otherwise, do not change the interface!!! 

---

## Part 2: Character Subclasses (2-3 hours)

Create **4 character subclasses** based on your Lab 1 design. Each subclass should:
- Inherit from `Character`
- Have different base stats
- Have at least one unique method (special ability)

1. Pick your favorite character classes from Lab 1
2. Decide on their stats (HP, attack, defense, speed)
3. Implement them in `character.py`
4. Give each one at least one special ability method. Again, how you do this is up to you. 

Make sure to change the class names from `Character1`, `Character2`, etc. to your specific class names.

---

## Part 3: Testing (1-2 hours)

Create a file called `code/tests/test_character.py` that tests your character classes.

### Required Tests
````python
# test_character.py

from character import Character1, Character2, Character3, Character4  # Import your classes

def test_character_creation():
    """Test creating a basic character"""
    print("Testing character creation...")
    
    # Create a character
    hero = Character1("Hero", hp=100, attack=15, defense=10, speed=6)
    
    # Verify attributes are set correctly
    assert hero.name == "Hero"
    assert hero.hp == 100
    assert hero.max_hp == 100
    assert hero.attack == 15
    assert hero.defense == 10
    assert hero.speed == 6
    
    print("✓ Character creation works!")

def test_take_damage():
    """Test taking damage"""
    print("Testing take_damage...")
    
    # Create a character
    hero = Character1("Hero", hp=100, attack=15, defense=10, speed=6)
    
    # Apply damage
    actual_damage = hero.take_damage(20)
    
    # TODO: Verify damage calculation (20 - 10 defense = 10 actual)
    assert actual_damage == 10
    assert hero.hp == 90
    
    print("✓ Taking damage works!")

def run_all_tests():
    """Run all tests"""
    print("="*50)
    print("Running Character Tests")
    print("="*50)
    
    test_character_creation()
    test_take_damage()
    
    print("="*50)
    print("All tests passed! ✓")
    print("="*50)

if __name__ == "__main__":
    run_all_tests()
````

### Your Additional Tests

Add tests for YOUR character classes:
- Test each special ability.
- Test edge cases (what if HP is 0?). You may use AI to think of edge cases that need testing, but may not use AI for coding your tests. Remember to include all AI conversations in your submission. 
- Test class-specific attributes.

**Minimum:** 10 test functions total. 

---

## Part 4: Logo and Character Sprites with AI (1-2 hours)

Use AI image generation to create sprites for your character classes. These are the images that will go in your game. The game is fairly basic at this point (think Atari), so you may want simple pixel art, but the choice is yours. 

### Requirements

Generate a **logo** for your game. 
- Use DALL-E, Midjourney, Stable Diffusion, or similar
- Images should be consistent in style
- Save as PNG files
- There is a sample file under the `graphics` folder
- The sample file is 460x150 (width x height)

Generate **4 character sprites** (one for each subclass you created):
- Use DALL-E, Midjourney, Stable Diffusion, or similar
- Images should be consistent in style
- Save as PNG files
- 64x64 or 128x128 pixels works well for game sprites

### Example Prompts
````
"A warrior character sprite for a video game, pixel art style, 
holding a sword and shield, wearing armor, front view, 64x64 pixels, 
transparent background"

"A mage character sprite for a video game, pixel art style, 
wearing robes, holding a magical staff, front view, 64x64 pixels, 
transparent background"

"A rogue character sprite for a video game, pixel art style, 
wearing dark cloak, holding daggers, sneaky pose, front view, 
64x64 pixels, transparent background"
````

### Directory Structure

Under the `graphics` folder in your repository:
````
graphics/
├── characters/
│   ├── [your_class_1].png
│   ├── [your_class_2].png
│   ├── [your_class_3].png
│   └── [your_class_4].png
├── logo.png
└── sprite_prompts.md  # Document your prompts
````

### Document Your Prompts

Create `graphics/sprite_prompts.md`:
````markdown
# Character Sprite Generation Prompts

## Warrior
**Tool Used:** DALL-E 3
**Prompt:** "A warrior character sprite..."
**Iterations:** 3 (adjusted armor color on 2nd try)
**Final Result:** warrior.png

## Mage
**Tool Used:** DALL-E 3
**Prompt:** "A mage character sprite..."
**Iterations:** 2
**Final Result:** mage.png

[etc.]
````

---

## Part 5: Documentation (30 minutes)

### Update Your README

Update your repository's `README.md`:
````markdown
# [Mlb pro manager]

## Description
You enter the league at a turning point in its history. Owners demand results, fans crave legends, and technology has transformed how talent is found and developed. Every organization competes for the same scarce resources: elite players, visionary coaches, and the infrastructure that turns potential into performance. The minor leagues are no longer just a proving ground, they are a pipeline where tomorrow’s stars wait for a call that can change everything. 

As General Manager, you command the entire ecosystem of a club. You negotiate trades that can redefine rivalries, place aggressive bids on free agents who promise immediate impact, and decide when a young prospect is ready to leave the bus rides behind and step onto the main stage. Beyond the roster, you invest in training facilities, analytics labs, and medical centers that shape careers and extend primes. You hire coaches who mold talent and vendors who keep the organization running smoothly. 

Every season is a test of vision and nerve. Build wisely, adapt quickly, and leave a legacy that echoes through baseball history. 

## Labs Completed
- [x] Lab 1: Game Design
- [x] Lab 2: Character System

## Character Classes Implemented

### Coach
- boost players stats
- Special Ability: motivational speech (stamina +40)
- Stats: ops_plus = 50, average_plus = 40, slugging_plus = 50

### Pitcher
- Most important player on your defense, worth investing in
- Special Ability: Hot streak (boosts avg modifier and slugging modifier)
- Stats: avg_modifier = -50, slg_modifier = -40, stamina = 100

### Catcher
- commands the defense from behind the plate plus has a powerful bat
- Special Ability: steady hand (boost the pitchers stats for an game)
- Stats: ops = 900, average = 250, slugging = 600

### Second Baseman
- valuable player on defense and a consistent hitter on offense.
- Special Ability: turn two (can turn one out into two when there's a runner on first)
- Stats: ops = 700, average = 300, slugging = 450

## How to Run

### Run Tests
```bash
python3 test_character.py
```

### Run Demo
```bash
python3 main.py
```

## Files
- `character.py` - Character class implementations
- `test_character.py` - Unit tests
- `graphics/game characters/` - Logo + Character sprites
````

### Add Code Comments

Make sure your code has:
- Docstrings for every class and method
- Comments explaining complex logic
- Your name and date at the top of each file

Example:
````python
"""
character.py - Character class system for [Your Game Name]

Author: [Your Name]
Date: [Today's Date]
Course: Data Structures & Algorithms
Lab: Lab 2 - Character System
"""

# [rest of your code]
````

---

## Part 6: Play your game as your character

To run your game:
### Run Demo
```bash
python main.py
```

This should open your game. Once you start the game you will be taken to a character selection window. If done properly, you should be able to select and play as your characters.

---

## Deliverables

Your repository should contain:
````
lab_02/
├── code/
│   └── tests/
│   │   └── test_character.py     # All tests (10+ test functions)
│   └── character.py              # Character base class + subclasses
├── graphics/
│   └── characters/
│   │   ├── [your_class_1].png
│   │   ├── [your_class_2].png
│   │   ├── [your_class_3].png
│   │   └── [your_class_4].png
│   ├── logo.png
│   └── sprite_prompts.md     # AI prompts for sprites
├── ai_conversations.md       # The full dump of your AI conversations
├── lab2_summary.md           # Summary and reflection
└── README.md                 # Updated with Lab 2 info

````

### Create lab2_summary.md
````markdown
# Lab 2 Summary

## Character Classes Implemented
[List each class with brief description]

## Special Abilities
[Describe each unique ability you implemented]

## Testing Approach
[Describe how you tested your code. What edge cases did you consider?]

## Challenges Faced
[What was difficult? How did you overcome it?]

## What I Learned
[Key takeaways about OOP, inheritance, Python, etc.]

## AI Usage for Sprites
[Which tool did you use? How many iterations? What worked well?]

## Time Spent
- Implementing Character class: [X hours]
- Implementing subclasses: [X hours]
- Testing: [X hours]
- Sprite generation: [X hours]
- Total: [X hours]
````

---

## Grading (30 points)

**Character Base Class (8 points)**
- Correct initialization: 2 pts
- `take_damage()` works correctly: 1 pts
- `heal()` works correctly: 1 pts
- `is_alive()` and other methods: 1 pts
- Proper use of protected and private methods with justification: 3 pts

**Character Subclasses (8 points)**
- 3-5 subclasses created: 3 pts
- Proper use of inheritance: 2 pts
- Unique special abilities: 3 pts

**Testing (5 points)**
- All required tests present: 3 pts
- Tests pass: 2 pts

**Character Sprites (4 points)**
- 3-5 sprites generated: 2 pts
- Consistent style: 1 pt
- Documented prompts: 1 pt

**Documentation & Code Quality (5 points)**
- Code comments and docstrings: 1 pt
- Full AI conversations: 2 pt
- Summary and README updated: 2 pt

---

## Due Date
**Sunday, January 25, 2025 at 11:59 PM Eastern**

---

## Getting Help

**Email:** salvatore.giorgi@temple.edu, zhicheng.huang@temple.edu
