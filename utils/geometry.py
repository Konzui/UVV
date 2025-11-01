"""Simple geometry classes for drawing"""

import blf
from dataclasses import dataclass


@dataclass
class Rectangle:
    """Basic rectangle with normalized bounds"""
    left: float = 0.0
    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0
    auto_normalize: bool = True

    @property
    def width(self):
        return self.right - self.left

    @width.setter
    def width(self, val):
        self.right = self.left + val

    @property
    def height(self):
        return self.top - self.bottom

    @height.setter
    def height(self, val):
        self.top = self.bottom + val

    def __post_init__(self):
        if self.auto_normalize:
            self.normalize()

    def normalize(self):
        """Ensure left < right and bottom < top"""
        p_left = min(self.left, self.right)
        p_right = max(self.left, self.right)
        p_bottom = min(self.top, self.bottom)
        p_top = max(self.top, self.bottom)

        self.left = p_left
        self.top = p_top
        self.right = p_right
        self.bottom = p_bottom

    def center(self):
        """Get center point of rectangle"""
        return (self.left + self.width / 2, self.bottom + self.height / 2)

    def intersects(self, other):
        """Check if this rectangle intersects with another"""
        if self.left > other.right or self.right < other.left:
            return False

        if self.top < other.bottom or self.bottom > other.top:
            return False

        return True

    def __hash__(self):
        return hash((self.left, self.top, self.right, self.bottom))


@dataclass
class TextRect(Rectangle):
    """Rectangle with text rendering capabilities"""
    name: str = ''
    color: tuple = (1.0, 1.0, 1.0, 1.0)

    def __hash__(self):
        return hash((super().__hash__(), self.name, self.color))

    def draw_text(self):
        """Draw text at the rectangle position with shadow"""
        # Set text position
        blf.position(0, self.left, self.bottom, 0)

        # Set text color
        blf.color(0, *self.color)

        # Enable shadow for better visibility
        blf.enable(0, blf.SHADOW)
        blf.shadow(0, 3, 0.0, 0.0, 0.0, 1.0)
        blf.shadow_offset(0, 1, -1)

        # Draw the text
        blf.draw(0, self.name)

        # Clean up shadow
        blf.disable(0, blf.SHADOW)
