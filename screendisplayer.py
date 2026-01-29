import pygame
import sys
import random
import time
from datetime import datetime  # Used in _substitute_variables for dynamic variable substitution (e.g. timestamps)
from typing import List, Tuple, Dict, Optional, Union
from letter_dictionary import letter_dict
from screen_overlay import ScreenOverlay
from colour_schemes import list_colour_schemes
from config.enums import DisplayType, ColourScheme, TransitionMode
from config.settings import Settings
from logger_setup import setup_logger

logger = setup_logger(__name__)

class ScreenDisplayer:
    def __init__(self, grid_width: int = 20, grid_height: int = 10, square_size: int = 30, 
                 display_scale: float = 1.0, display_type: DisplayType = DisplayType.PIXEL_GRID,
                 settings: Optional[Settings] = None):
        logger.info(f"Initializing ScreenDisplayer: {grid_width}x{grid_height}, square_size={square_size}, scale={display_scale}, type={display_type.name}")
        
        # Store settings reference, create default if none provided
        self.settings = settings if settings is not None else Settings.create_default()
        
        # Store display type for future extensibility
        self.display_type = display_type
        
        self.grid_width = grid_width
        self.grid_height = grid_height
        self.square_size = square_size
        self.display_scale = display_scale
        
        # Logical dimensions (what the math thinks)
        self.logical_width = grid_width * square_size
        self.logical_height = grid_height * square_size
        
        # Physical screen dimensions (what actually displays)
        self.screen_width = int(self.logical_width * display_scale)
        self.screen_height = int(self.logical_height * display_scale)
        
        logger.info(f"Screen dimensions: {self.screen_width}x{self.screen_height}")
        
        # Colour definitions
        self.colours = {
            'black': (0, 0, 0),
            'white': (255, 255, 255),
            'red': (255, 0, 0),
            'green': (0, 255, 0),
            'blue': (0, 0, 255),
            'yellow': (255, 255, 0),
            'cyan': (0, 255, 255),
            'magenta': (255, 0, 255)
        }
        
        # Initialise grid (0 = black/off, 1 = white/on by default)
        self.grid = [[0 for _ in range(grid_width)] for _ in range(grid_height)]
        self.selected_colour = self.colours['black']  # Changed from white to black
        self.text_content = []  # Store loaded text blocks
        
        # Pygame setup
        try:
            self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
            pygame.display.set_caption("Screen Displayer")
            self.clock = pygame.time.Clock()
            self.running = True
            logger.info("Pygame display initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing pygame display: {e}")
            raise
        
        # Add transition system
        self.current_grid = [[False for _ in range(grid_width)] for _ in range(grid_height)]
        self.target_grid = [[False for _ in range(grid_width)] for _ in range(grid_height)]
        self.current_outline_grid = [[False for _ in range(grid_width)] for _ in range(grid_height)]
        self.target_outline_grid = [[False for _ in range(grid_width)] for _ in range(grid_height)]
        self.current_outline_alpha_grid = [[0.0 for _ in range(grid_width)] for _ in range(grid_height)]  # Alpha values for outline pixels
        self.target_outline_alpha_grid = [[0.0 for _ in range(grid_width)] for _ in range(grid_height)]
        self.outline_fade_state_grid = [[0 for _ in range(grid_width)] for _ in range(grid_height)]  # 0=inactive, 1=fading_in, -1=fading_out
        self.transition_pixels = []  # List of (row, col) pixels that need to change
        self.outline_transition_pixels = []  # List of (row, col) outline pixels that need to change
        self.is_transitioning = False
        self.transition_speed = 5.0  # pixels to change per frame (now supports fractional values)
        self.transition_accumulator = 0.0  # Accumulates fractional pixel changes
        self.transition_start_time = 0  # For timing logs
        
        # Map text pixels to their outline neighbors for instant outline appearance
        self.text_to_outline_map: dict[tuple[int, int], list[tuple[int, int]]] = {}
        # Reverse map: outline pixels to all their adjacent text pixels
        self.outline_to_text_map: dict[tuple[int, int], set[tuple[int, int]]] = {}
        self.text_pending_deletion: set[tuple[int, int]] = set()  # Text pixels waiting for outline to fade
        
        # TODO: Add these outline opacity values to settings/options
        self.outline_opacity_min = 0.1  # Minimum opacity for outline pixels (10%)
        self.outline_opacity_max = 0.35  # Maximum opacity for outline pixels (35%)
        self.outline_opacity_lerp_speed = 0.2  # How fast outline opacity changes (0.0-1.0 per frame)
        
        # Add overlay system
        self.overlay = ScreenOverlay(grid_width, grid_height, square_size, display_scale, self.settings)
        self.overlay_enabled = True
        
        logger.info("ScreenDisplayer initialization complete")
    
    def _generate_outline_grid(self, text_grid: List[List[bool]]) -> List[List[bool]]:
        """Generate an outline grid from a text grid.
        
        For each True pixel in text_grid, mark all 8 adjacent neighbors as outline pixels,
        but only if they're not already text pixels. Also generates random alpha values.
        """
        outline_grid = [[False for _ in range(self.grid_width)] for _ in range(self.grid_height)]
        
        # Define 8-directional neighbors (up, down, left, right, and diagonals)
        neighbors = [
            (-1, -1), (-1, 0), (-1, 1),  # top-left, top, top-right
            (0, -1),           (0, 1),    # left, right
            (1, -1),  (1, 0),  (1, 1)     # bottom-left, bottom, bottom-right
        ]
        
        # For each text pixel, mark its neighbors as outline
        for row in range(self.grid_height):
            for col in range(self.grid_width):
                if text_grid[row][col]:  # If this is a text pixel
                    # Check all 8 neighbors
                    for dy, dx in neighbors:
                        neighbor_row = row + dy
                        neighbor_col = col + dx
                        
                        # Check bounds
                        if 0 <= neighbor_row < self.grid_height and 0 <= neighbor_col < self.grid_width:
                            # Only mark as outline if it's NOT a text pixel
                            if not text_grid[neighbor_row][neighbor_col]:
                                outline_grid[neighbor_row][neighbor_col] = True
                                # Generate random alpha for this outline pixel (ghostly effect)
                                alpha = random.uniform(self.outline_opacity_min, self.outline_opacity_max)
                                self.target_outline_alpha_grid[neighbor_row][neighbor_col] = alpha
        
        return outline_grid
    
    def _build_text_to_outline_map(self) -> None:
        """Build a mapping from each text pixel to its outline neighbors.
        Also builds reverse map from outline to all adjacent text pixels.
        
        This allows outline pixels to appear instantly when their core text
        pixel appears during transitions.
        """
        self.text_to_outline_map = {}
        self.outline_to_text_map = {}
        
        # Define 8-directional neighbors
        neighbors = [
            (-1, -1), (-1, 0), (-1, 1),
            (0, -1),           (0, 1),
            (1, -1),  (1, 0),  (1, 1)
        ]
        
        # For each text pixel, find its outline neighbors
        for row in range(self.grid_height):
            for col in range(self.grid_width):
                if self.target_grid[row][col]:  # If this is a text pixel
                    outline_neighbors = []
                    
                    # Check all 8 neighbors
                    for dy, dx in neighbors:
                        neighbor_row = row + dy
                        neighbor_col = col + dx
                        
                        # Check bounds
                        if 0 <= neighbor_row < self.grid_height and 0 <= neighbor_col < self.grid_width:
                            # If neighbor is an outline pixel (not text)
                            if self.target_outline_grid[neighbor_row][neighbor_col] and not self.target_grid[neighbor_row][neighbor_col]:
                                outline_neighbors.append((neighbor_row, neighbor_col))
                                
                                # Build reverse map: this outline touches this text
                                outline_key = (neighbor_row, neighbor_col)
                                if outline_key not in self.outline_to_text_map:
                                    self.outline_to_text_map[outline_key] = set()
                                self.outline_to_text_map[outline_key].add((row, col))
                    
                    if outline_neighbors:
                        self.text_to_outline_map[(row, col)] = outline_neighbors
    
    def _substitute_variables(self, text: str) -> str:
        """Substitute variables in text like [[DATE]] with actual values"""
        # Get current date in DD MM YYYY format
        current_date = datetime.now().strftime("%d %m %Y")
        
        # Replace variables
        text = text.replace("[[DATE]]", current_date)
        
        return text
    
    def load_text_file(self, filepath: str) -> None:
        """Load text from file and save to class variable as blocks separated by empty lines"""
        try:
            with open(filepath, 'r') as file:
                content = file.read()
            
            # Substitute variables before processing
            content = self._substitute_variables(content)
            
            # Split content into blocks separated by empty lines
            blocks = []
            current_block = []
            
            for line in content.splitlines():
                if line.strip() == "":  # Empty line - start new block
                    if current_block:  # Only add non-empty blocks
                        blocks.append("\n".join(current_block))
                        current_block = []
                else:
                    current_block.append(line)
            
            # Add final block if it exists
            if current_block:
                blocks.append("\n".join(current_block))
            
            self.text_content = blocks
            logger.info(f"Loaded {len(blocks)} text blocks from {filepath}")
            
        except FileNotFoundError:
            logger.warning(f"File {filepath} not found. Using empty text.")
            self.text_content = []
        except Exception as e:
            logger.error(f"Error loading file: {e}")
            self.text_content = []
    
    def start_transition_to_text(self, block_index: int) -> None:
        """Start a transition to new text content"""
        if block_index < len(self.text_content):
            start_time = time.time()
            logger.debug(f"Starting transition to block {block_index} at {start_time:.3f}")
            
            # Create target grid with new text
            self.target_grid = [[False for _ in range(self.grid_width)] for _ in range(self.grid_height)]
            self._render_text_to_grid(self.text_content[block_index], self.target_grid)
            
            # Generate outline grid from the text grid
            self.target_outline_grid = self._generate_outline_grid(self.target_grid)
            
            # Build map of text pixels to their outline neighbors
            self._build_text_to_outline_map()
            
            # Find all text pixels that need to change
            self.transition_pixels = []
            for row in range(self.grid_height):
                for col in range(self.grid_width):
                    if self.current_grid[row][col] != self.target_grid[row][col]:
                        self.transition_pixels.append((row, col))
            
            # Find all outline pixels that need to change
            self.outline_transition_pixels = []
            for row in range(self.grid_height):
                for col in range(self.grid_width):
                    if self.current_outline_grid[row][col] != self.target_outline_grid[row][col]:
                        self.outline_transition_pixels.append((row, col))
            
            setup_time = time.time() - start_time
            total_pixels = len(self.transition_pixels) + len(self.outline_transition_pixels)
            logger.debug(f"Text transition setup: {len(self.transition_pixels)} text pixels, {len(self.outline_transition_pixels)} outline pixels, setup took {setup_time*1000:.1f}ms")
            logger.debug(f"Estimated transition time: {total_pixels / self.transition_speed:.1f} frames at {self.transition_speed} px/frame")
            
            # Randomize the order of pixel changes
            random.shuffle(self.transition_pixels)
            random.shuffle(self.outline_transition_pixels)
            self.is_transitioning = True
            self.transition_start_time = time.time()
    
    def start_transition_to_blank(self) -> None:
        """Start a transition to blank/empty display"""
        start_time = time.time()
        logger.debug(f"Starting transition to blank display at {start_time:.3f}")
        
        # Create target grid with empty text (much faster than transitioning all pixels)
        self.target_grid = [[False for _ in range(self.grid_width)] for _ in range(self.grid_height)]
        self._render_text_to_grid("", self.target_grid)  # Render empty string
        
        # Empty text has no outline
        self.target_outline_grid = [[False for _ in range(self.grid_width)] for _ in range(self.grid_height)]
        
        # Build map of current text pixels to their outline neighbors (for fade-out)
        # Save current grid state before it changes
        old_target_grid = [[self.current_grid[row][col] for col in range(self.grid_width)] for row in range(self.grid_height)]
        # Temporarily set target to current for mapping
        temp_target = self.target_grid
        self.target_grid = old_target_grid
        self._build_text_to_outline_map()
        self.target_grid = temp_target  # Restore actual blank target
        
        # Find text pixels that need to change
        self.transition_pixels = []
        for row in range(self.grid_height):
            for col in range(self.grid_width):
                if self.current_grid[row][col] != self.target_grid[row][col]:
                    self.transition_pixels.append((row, col))
        
        # Find outline pixels that need to change
        self.outline_transition_pixels = []
        for row in range(self.grid_height):
            for col in range(self.grid_width):
                if self.current_outline_grid[row][col] != self.target_outline_grid[row][col]:
                    self.outline_transition_pixels.append((row, col))
        
        setup_time = time.time() - start_time
        total_pixels = len(self.transition_pixels) + len(self.outline_transition_pixels)
        logger.debug(f"Blank transition setup: {len(self.transition_pixels)} text pixels, {len(self.outline_transition_pixels)} outline pixels to turn off, setup took {setup_time*1000:.1f}ms")
        logger.debug(f"Estimated transition time: {total_pixels / self.transition_speed:.1f} frames at {self.transition_speed} px/frame")
        
        # Randomize the order of pixel changes
        random.shuffle(self.transition_pixels)
        random.shuffle(self.outline_transition_pixels)
        self.is_transitioning = True
        self.transition_start_time = time.time()
    
    def update_transition(self) -> None:
        """Update the transition animation - call this each frame"""
        if not self.is_transitioning or (not self.transition_pixels and not self.outline_transition_pixels):
            self.is_transitioning = False
            return
        
        # Add this frame's transition speed to the accumulator
        self.transition_accumulator += self.transition_speed
        
        # Calculate total pixels to change (text + outline)
        total_remaining = len(self.transition_pixels) + len(self.outline_transition_pixels)
        pixels_to_change = min(int(self.transition_accumulator), total_remaining)
        
        # Subtract the pixels we're actually changing from the accumulator
        self.transition_accumulator -= pixels_to_change
        
        # Change pixels (text pixels trigger their outline neighbors)
        for _ in range(pixels_to_change):
            if self.transition_pixels:
                # Pop a text pixel and update it
                row, col = self.transition_pixels.pop()
                old_value = self.current_grid[row][col]
                new_value = self.target_grid[row][col]
                self.current_grid[row][col] = new_value
                
                # Handle outline neighbors based on whether text is appearing or disappearing
                if (row, col) in self.text_to_outline_map:
                    for outline_row, outline_col in self.text_to_outline_map[(row, col)]:
                        if new_value and not old_value:
                            # Text pixel appearing - add outline at full opacity instantly
                            self.current_outline_grid[outline_row][outline_col] = True
                            self.current_outline_alpha_grid[outline_row][outline_col] = self.target_outline_alpha_grid[outline_row][outline_col]
                        elif not new_value and old_value:
                            # Text pixel disappearing - check if outline still has ANY text neighbor IN TARGET
                            has_text_neighbor = False
                            
                            # Check all 8 neighbors of this outline pixel
                            for dy in [-1, 0, 1]:
                                for dx in [-1, 0, 1]:
                                    if dy == 0 and dx == 0:
                                        continue
                                    
                                    check_row = outline_row + dy
                                    check_col = outline_col + dx
                                    
                                    # Check bounds
                                    if 0 <= check_row < self.grid_height and 0 <= check_col < self.grid_width:
                                        # Check target grid - if text exists in final state, it's staying
                                        if self.target_grid[check_row][check_col]:
                                            has_text_neighbor = True
                                            break
                                
                                if has_text_neighbor:
                                    break
                            
                            # Remove outline instantly if it has NO text neighbors left
                            if not has_text_neighbor:
                                self.current_outline_grid[outline_row][outline_col] = False
                                self.current_outline_alpha_grid[outline_row][outline_col] = 0.0
                        
                        # Remove from outline transition list if present
                        if (outline_row, outline_col) in self.outline_transition_pixels:
                            self.outline_transition_pixels.remove((outline_row, outline_col))
            elif self.outline_transition_pixels:
                # Only orphaned outline pixels remain (outlines without text cores)
                row, col = self.outline_transition_pixels.pop()
                old_value = self.current_outline_grid[row][col]
                new_value = self.target_outline_grid[row][col]
                self.current_outline_grid[row][col] = new_value
                
                # Handle fade based on appearing or disappearing
                if new_value and not old_value:
                    # Appearing - start at 0 and fade in
                    self.current_outline_alpha_grid[row][col] = 0.0
                    self.outline_fade_state_grid[row][col] = 1
                elif not new_value and old_value:
                    # Disappearing - start fade out
                    self.outline_fade_state_grid[row][col] = -1
        
        # CLEANUP PASS: Remove ALL outline pixels that have no text neighbors in current grid
        for row in range(self.grid_height):
            for col in range(self.grid_width):
                if self.current_outline_grid[row][col]:
                    # This outline pixel exists - check if it has any text neighbors currently visible
                    has_text_neighbor = False
                    
                    for dy in [-1, 0, 1]:
                        for dx in [-1, 0, 1]:
                            if dy == 0 and dx == 0:
                                continue
                            
                            check_row = row + dy
                            check_col = col + dx
                            
                            if 0 <= check_row < self.grid_height and 0 <= check_col < self.grid_width:
                                if self.current_grid[check_row][check_col]:
                                    has_text_neighbor = True
                                    break
                        
                        if has_text_neighbor:
                            break
                    
                    # Remove outline if it has no text neighbors
                    if not has_text_neighbor:
                        self.current_outline_grid[row][col] = False
                        self.current_outline_alpha_grid[row][col] = 0.0
        
        # Check if transition is complete
        if not self.transition_pixels and not self.outline_transition_pixels:
            self.is_transitioning = False
            self.transition_accumulator = 0.0  # Reset accumulator when transition completes
            logger.debug("Transition complete")
            # Copy target to grid for compatibility with existing code
            self.grid = [[int(self.target_grid[row][col]) for col in range(self.grid_width)] for row in range(self.grid_height)]
    
    def display_text(self, block_index: int = 0) -> None:
        """Display a specific text block by starting a transition to it"""
        logger.debug(f"display_text called with block_index: {block_index}")
        
        if not self.text_content or block_index >= len(self.text_content):
            logger.warning("No text content or invalid block index")
            return
        
        # Use the transition system instead of immediate update
        self.start_transition_to_text(block_index)
    
    def set_selected_colour(self, colour_name: str) -> None:
        """Set the colour for lit squares"""
        if colour_name in self.colours:
            self.selected_colour = self.colours[colour_name]
            logger.info(f"Colour set to: {colour_name}")
    
    def update_grid(self, new_grid: List[List[int]]) -> None:
        """Update the grid with new data"""
        if len(new_grid) <= self.grid_height and all(len(row) <= self.grid_width for row in new_grid):
            self.grid = new_grid
    
    def set_transition_speed(self, speed: float) -> None:
        """Set how many pixels change per frame during transitions. Higher = faster. Supports fractional values."""
        self.transition_speed = max(0.1, speed)  # Ensure at least 0.1 pixels per frame
        logger.info(f"Transition speed set to: {speed} pixels per frame")
    
    def get_transition_speed(self) -> float:
        """Get the current transition speed."""
        return self.transition_speed
    
    def _render_text_to_grid(self, text_block: str, target_grid: list[list[bool]]) -> None:
        """Helper method to render text to a specific grid"""
        # Clear the target grid
        for row in range(len(target_grid)):
            for col in range(len(target_grid[row])):
                target_grid[row][col] = False
        
        # Handle empty string case (blank display)
        if not text_block or text_block.strip() == "":
            # Empty string - grid is already cleared, nothing more to do
            return
        
        # Split text into lines
        lines = text_block.splitlines()
        
        # Convert text to grid using letter dictionary (character dimensions from settings)
        char_width = self.settings.text_rendering.char_width
        char_height = self.settings.text_rendering.char_height
        spacing_x = self.settings.text_rendering.spacing_x
        spacing_y = self.settings.text_rendering.spacing_y
        
        # Calculate total text height for vertical centering
        text_height = len(lines) * (char_height + spacing_y) - spacing_y
        start_y = (self.grid_height - text_height) // 2
        
        for row, line in enumerate(lines):
            if row * (char_height + spacing_y) + start_y >= self.grid_height:
                break
            
            # Trim the line to remove leading/trailing spaces for accurate centering
            trimmed_line = line.strip()
            
            # Calculate horizontal centering for this specific trimmed line
            line_width = len(trimmed_line) * (char_width + spacing_x) - spacing_x if trimmed_line else 0
            start_x = (self.grid_width - line_width) // 2
                
            for col, char in enumerate(trimmed_line):
                if col * (char_width + spacing_x) + start_x >= self.grid_width:
                    break
                    
                # Get character pattern from dictionary
                char_pattern = letter_dict.get(char.upper(), letter_dict.get(' ', []))
                
                # Place character pattern in grid with spacing and centering
                for y in range(min(char_height, len(char_pattern))):
                    if row * (char_height + spacing_y) + start_y + y >= self.grid_height or row * (char_height + spacing_y) + start_y + y < 0:
                        break
                    for x in range(char_width):
                        grid_x = col * (char_width + spacing_x) + start_x + x
                        grid_y = row * (char_height + spacing_y) + start_y + y
                        
                        if 0 <= grid_x < self.grid_width and 0 <= grid_y < self.grid_height:
                            # Extract bit from binary pattern
                            bit_value = (char_pattern[y] >> (char_width - 1 - x)) & 1
                            target_grid[grid_y][grid_x] = bool(bit_value)
    
    def draw_grid(self) -> None:
        """Draw the current grid state with overlay effects"""
        self.screen.fill(self.colours['black'])
        
        pixels_drawn = 0
        
        # First pass: Render overlay effects (ghosts behind outline)
        if self.overlay_enabled:
            self.overlay.update_effects(self.current_grid)
            self.overlay.render_overlay(self.screen, self.selected_colour)
        
        # Second pass: Draw white outline pixels with lerped opacity (on top of ghosts)
        # Pre-create a reusable surface for outline pixels to avoid per-pixel allocations
        outline_width = int(self.square_size * self.display_scale)
        outline_height = int(self.square_size * self.display_scale)
        outline_surface = pygame.Surface((outline_width, outline_height))
        outline_surface.fill(self.colours['white'])

        # Draw outline pixels
        for row in range(self.grid_height):
            for col in range(self.grid_width):
                if self.current_outline_alpha_grid[row][col] > 0.001:
                    x = int(col * self.square_size * self.display_scale)
                    y = int(row * self.square_size * self.display_scale)
                    
                    # Get alpha value for this pixel
                    alpha = self.current_outline_alpha_grid[row][col]
                    outline_surface.set_alpha(int(255 * alpha))  # Convert 0.0-1.0 to 0-255
                    self.screen.blit(outline_surface, (x, y))
                    pixels_drawn += 1
        
        # Third pass: Draw text pixels (on top of outline)
        for row in range(self.grid_height):
            for col in range(self.grid_width):
                if self.current_grid[row][col]:  # Use current_grid instead of grid
                    x = int(col * self.square_size * self.display_scale)
                    y = int(row * self.square_size * self.display_scale)
                    width = int(self.square_size * self.display_scale)
                    height = int(self.square_size * self.display_scale)
                    pygame.draw.rect(self.screen, self.selected_colour, (x, y, width, height))
                    pixels_drawn += 1
        
        # Debug output occasionally
        if hasattr(self, '_debug_counter'):
            self._debug_counter += 1
        else:
            self._debug_counter = 0
            
        if self._debug_counter % self.settings.debug.debug_output_interval == 0:
            logger.debug(f"Drew {pixels_drawn} pixels")
            if self.overlay_enabled:
                stats = self.overlay.get_effect_stats()
                logger.debug(f"Overlay effects - Ghost: {stats['ghost_pixels']}, Flicker: {stats['flicker_pixels']}")
    
    def handle_events(self) -> None:
        """Handle pygame events"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_o:  # Toggle overlay
                    self.overlay_enabled = not self.overlay_enabled
                    logger.info(f"Overlay effects: {'ON' if self.overlay_enabled else 'OFF'}")
                elif event.key == pygame.K_c:  # Clear overlay effects
                    self.overlay.clear_effects()
                    logger.info("Overlay effects cleared")
                elif event.key == pygame.K_t:  # Cycle through colour schemes
                    # Get current scheme from overlay directly
                    current_scheme = self.overlay.colour_scheme_name
                    all_schemes = list(ColourScheme)
                    
                    # Find current scheme enum
                    current_enum = ColourScheme.from_string(current_scheme)
                    
                    try:
                        current_index = all_schemes.index(current_enum)
                        next_index = (current_index + 1) % len(all_schemes)
                    except ValueError:
                        next_index = 0
                    
                    next_scheme = all_schemes[next_index]
                    self.set_ghost_colour_scheme(next_scheme)
                    logger.info(f"Colour scheme changed to: {next_scheme.value}")
                elif event.key == pygame.K_m:  # Toggle colour transition mode
                    # Get current mode from overlay directly
                    current_mode = self.overlay.colour_transition_mode
                    
                    # Cycle through enum modes
                    if current_mode == TransitionMode.SMOOTH:
                        new_mode = TransitionMode.SNAP
                    elif current_mode == TransitionMode.SNAP:
                        new_mode = TransitionMode.MIXED
                    elif current_mode == TransitionMode.MIXED:
                        new_mode = TransitionMode.SPREAD_HORIZONTAL
                    elif current_mode == TransitionMode.SPREAD_HORIZONTAL:
                        new_mode = TransitionMode.SPREAD_VERTICAL
                    elif current_mode == TransitionMode.SPREAD_VERTICAL:
                        new_mode = TransitionMode.SPREAD_DIAGONALLY_DOWN
                    elif current_mode == TransitionMode.SPREAD_DIAGONALLY_DOWN:
                        new_mode = TransitionMode.SPREAD_DIAGONALLY_UP
                    else:  # SPREAD_DIAGONALLY_UP
                        new_mode = TransitionMode.SMOOTH
                    
                    self.set_colour_transition_mode(new_mode)
                    logger.info(f"Colour transition mode changed to: {new_mode.value}")
    
    def configure_overlay_effects(self, ghost_chance: Optional[float] = None, ghost_decay: Optional[float] = None,
                                flicker_chance: Optional[float] = None, flicker_intensity: Optional[float] = None,
                                colour_scheme: Union[ColourScheme, str, None] = None, 
                                colour_transition_mode: Union[TransitionMode, str, None] = None,
                                snap_duration: Optional[int] = None,
                                enable_colour_averaging: Optional[bool] = None,
                                colour_averaging_interval: Optional[int] = None) -> None:
        """Configure overlay effect parameters using enums or strings"""
        # Set default ghost parameters for outline effect
        if ghost_chance is None:
            ghost_chance = 0.15  # Higher chance for better outline effect
        
        # Only pass parameters that were actually provided to avoid sending None to functions that expect floats
        ghost_kwargs = {}
        if ghost_chance is not None:
            ghost_kwargs['chance'] = ghost_chance
        if ghost_decay is not None:
            ghost_kwargs['decay'] = ghost_decay
        if ghost_kwargs:
            self.overlay.set_ghost_parameters(**ghost_kwargs)

        flicker_kwargs = {}
        if flicker_chance is not None:
            flicker_kwargs['chance'] = flicker_chance
        if flicker_intensity is not None:
            flicker_kwargs['intensity'] = flicker_intensity
        if flicker_kwargs:
            self.overlay.set_flicker_parameters(**flicker_kwargs)
        
        # Set colour scheme if provided
        if colour_scheme is not None:
            self.overlay.set_colour_scheme(colour_scheme)
        
        # Set colour transition mode if provided
        if colour_transition_mode is not None:
            self.overlay.set_colour_transition_mode(colour_transition_mode, snap_duration)
        
        # Set colour averaging parameters if provided
        colour_averaging_kwargs = {}
        if enable_colour_averaging is not None:
            colour_averaging_kwargs['enabled'] = enable_colour_averaging
        if colour_averaging_interval is not None:
            colour_averaging_kwargs['interval'] = colour_averaging_interval
        if colour_averaging_kwargs:
            self.overlay.set_colour_averaging_parameters(**colour_averaging_kwargs)
    
    def set_colour_transition_mode(self, mode: Union[TransitionMode, str], snap_duration: Optional[int] = None) -> bool:
        """Set the colour transition mode using TransitionMode enum or string."""
        return self.overlay.set_colour_transition_mode(mode, snap_duration)
    
    def set_ghost_colour_scheme(self, scheme: Union[ColourScheme, str]) -> bool:
        """Set the ghost colour scheme using ColourScheme enum or string."""
        return self.overlay.set_colour_scheme(scheme)
    
    def set_custom_ghost_colours(self, colours: List[Tuple[int, int, int]]) -> bool:
        """Set custom colours for ghost effects"""
        return self.overlay.set_custom_colour_scheme(colours)
    
    def get_available_colour_schemes(self) -> List[str]:
        """Get list of available colour scheme names"""
        return list_colour_schemes()
    
    def get_display_type(self) -> DisplayType:
        """Get the current display type."""
        return self.display_type
    
    def set_display_type(self, display_type: DisplayType) -> None:
        """Set the display type. Note: Currently only PIXEL_GRID is implemented."""
        if display_type != DisplayType.PIXEL_GRID:
            logger.warning(f"Display type {display_type.name} not yet implemented. Using PIXEL_GRID.")
            display_type = DisplayType.PIXEL_GRID
        self.display_type = display_type
        logger.info(f"Display type set to: {display_type.name}")
    
    def run(self, fps: int = 60, transition_manager=None) -> None:
        """Main display loop with optional transition manager"""
        logger.info(f"Starting main loop at {fps} FPS")
        
        while self.running:
            # Handle events
            self.handle_events()
            
            # Update transition manager if provided
            if transition_manager:
                transition_manager.update()
            
            # Update transition animation
            self.update_transition()
            
            # Draw everything
            self.draw_grid()
            pygame.display.flip()
            
            # Control frame rate
            self.clock.tick(fps)
        
        logger.info("Main loop ended")