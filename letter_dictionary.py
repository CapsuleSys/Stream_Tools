"""
Character Pixel Dictionary - 6x8 Binary Grid Representations

This module provides a lookup dictionary mapping characters to their pixel-based
representations using a 6x8 grid format. Each character is defined as a list of
6 binary numbers, where each binary number represents a row of 8 pixels.

Binary Format:
--------------
Each row is represented as a 6-bit binary number (0b prefix), where:
- 1 (bit set) = pixel ON (character foreground)
- 0 (bit cleared) = pixel OFF (character background)

Example: Letter 'A'
-------------------
    0b011111  →  .#####  (row 1: top horizontal bar)
    0b100001  →  #....#  (row 2: left and right verticals)
    0b100001  →  #....#  (row 3: left and right verticals)
    0b111111  →  ######  (row 4: middle horizontal bar)
    0b100001  →  #....#  (row 5: left and right verticals)
    0b100001  →  #....#  (row 6: left and right verticals bottom)

Usage:
------
    from letter_dictionary import letter_dict
    
    # Get pixel pattern for letter 'A'
    pattern = letter_dict['A']
    
    # Check if pixel at row 0, col 1 is set
    is_set = bool(pattern[0] & (1 << (5 - 1)))  # True (pixel is ON)

Grid Dimensions:
----------------
- Width: 6 pixels (bits 0-5, right to left)
- Height: 8 rows (list indices 0-7, though some chars use only 6)
- Total pixels per character: 48 (6 × 8)

Supported Characters:
---------------------
- Uppercase letters: A-Z
- Lowercase letters: a-z
- Digits: 0-9
- Punctuation: . , ! ? ' " : ; - ( ) [ ]
- Symbols: @ # $ % & * + = / \\ < > ^ _ ~ `
- Whitespace: space

Note: Characters not in the dictionary will be rendered as a blank space.
"""

# Provide a lookup dictionary for letters and characters to pixel representations in a 6x8 grid
letter_dict = {
    ' ': [
        0b000000,
        0b000000,
        0b000000,
        0b000000,
        0b000000,
        0b000000,
    ],
    'A': [
        0b011111,
        0b100001,
        0b100001,
        0b111111,
        0b100001,
        0b100001,
    ],
    'B': [
        0b111110,
        0b100001,
        0b100001,
        0b111110,
        0b100001,
        0b111110,
    ],
    'C': [
        0b011111,
        0b100000,
        0b100000,
        0b100000,
        0b100000,
        0b011111,
    ],
    'D': [
        0b111110,
        0b100001,
        0b100001,
        0b100001,
        0b100001,
        0b111110,
    ],
    'E': [
        0b111111,
        0b100000,
        0b100000,
        0b111110,
        0b100000,
        0b111111,
    ],
    'F': [
        0b111111,
        0b100000,
        0b100000,
        0b111110,
        0b100000,
        0b100000,
    ],
    'G': [
        0b011111,
        0b100000,
        0b100000,
        0b100111,
        0b100001,
        0b011111,
    ],
    'H': [
        0b100001,
        0b100001,
        0b100001,
        0b111111,
        0b100001,
        0b100001,
    ],
    'I': [
        0b111111,
        0b001000,
        0b001000,
        0b001000,
        0b001000,
        0b111111,
    ],
    'J': [
        0b011111,
        0b000100,
        0b000100,
        0b000100,
        0b100100,
        0b011000,
    ],
    'K': [
        0b100001,
        0b100010,
        0b101100,
        0b111000,
        0b100100,
        0b100010,
    ],
    'L': [
        0b100000,
        0b100000,
        0b100000,
        0b100000,
        0b100000,
        0b111111,
    ],
    'M': [
        0b100001,
        0b110011,
        0b101101,
        0b100001,
        0b100001,
        0b100001,
    ],
    'N': [
        0b100001,
        0b110001,
        0b101001,
        0b100101,
        0b100011,
        0b100001,
    ],
    'O': [
        0b011110,
        0b100001,
        0b100001,
        0b100001,
        0b100001,
        0b011110,
    ],
    'P': [
        0b111110,
        0b100001,
        0b100001,
        0b111110,
        0b100000,
        0b100000,
    ],
    'Q': [
        0b011110,
        0b100001,
        0b100001,
        0b101001,
        0b100010,
        0b011101,
    ],
    'R': [
        0b111110,
        0b100001,
        0b100001,
        0b111110,
        0b100010,
        0b100001,
    ],
    'S': [
        0b011111,
        0b100000,
        0b100000,
        0b011110,
        0b000001,
        0b111110,
    ],
    'T': [
        0b111111,
        0b001000,
        0b001000,
        0b001000,
        0b001000,
        0b001000,
    ],
    'U': [
        0b100001,
        0b100001,
        0b100001,
        0b100001,
        0b100001,
        0b011110,
    ],
    'V': [
        0b100001,
        0b100001,
        0b100001,
        0b100001,
        0b010010,
        0b001100,
    ],
    'W': [
        0b100001,
        0b100001,
        0b100001,
        0b101101,
        0b110011,
        0b100001,
    ],
    'X': [
        0b100001,
        0b010010,
        0b001100,
        0b001100,
        0b010010,
        0b100001,
    ],
    'Y': [
        0b100001,
        0b100001,
        0b010010,
        0b001100,
        0b001100,
        0b001100,
    ],
    'Z': [
        0b111111,
        0b000010,
        0b000100,
        0b001000,
        0b010000,
        0b111111,
    ],
    '!': [
        0b000111,
        0b000111,
        0b001110,
        0b000100,
        0b110000,
        0b110000,
    ],
    '?': [
        0b011110,
        0b100111,
        0b001110,
        0b001100,
        0b110000,
        0b110000,
    ],
    '~': [
        0b000000,
        0b000000,
        0b011001,
        0b100110,
        0b000000,
        0b000000,
    ],
    '1': [
        0b001000,
        0b011000,
        0b001000,
        0b001000,
        0b001000,
        0b011100,
    ],
    '2': [
        0b011110,
        0b100001,
        0b000010,
        0b000100,
        0b011000,
        0b111111,
    ],
    '3': [
        0b011110,
        0b100001,
        0b000001,
        0b001110,
        0b000001,
        0b111110,
    ],
    '4': [
        0b100001,
        0b100001,
        0b100001,
        0b111111,
        0b000001,
        0b000001,
    ],
    '5': [
        0b111111,
        0b100000,
        0b100000,
        0b111110,
        0b000001,
        0b111110,
    ],
    '6': [
        0b011110,
        0b100000,
        0b100000,
        0b111110,
        0b100001,
        0b011110,
    ],
    '7': [
        0b111111,
        0b000001,
        0b000010,
        0b000100,
        0b001000,
        0b010000,
    ],
    '8': [
        0b011110,
        0b100001,
        0b100001,
        0b011110,
        0b100001,
        0b011110,
    ],
    '9': [
        0b011110,
        0b100001,
        0b100001,
        0b011111,
        0b000001,
        0b011110,
    ],
    '0': [
        0b011110,
        0b100001,
        0b100011,
        0b100101,
        0b100001,
        0b011110,
    ],
    '-': [
        0b000000,
        0b000000,
        0b000000,
        0b111111,
        0b000000,
        0b000000,
    ],
}