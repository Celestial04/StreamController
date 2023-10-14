"""
Author: Core447
Year: 2023

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
any later version.

This programm comes with ABSOLUTELY NO WARRANTY!

You should have received a copy of the GNU General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.
"""
# Import Python modules
import os
import threading
from PIL import Image, ImageDraw, ImageFont, ImageOps
from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.ImageHelpers import PILHelper
from PIL import Image, ImageSequence
from StreamDeck.Transport.Transport import TransportError
from time import sleep
import math
from copy import copy
import time
import cv2
from loguru import logger as log
import pickle
import gzip

# Import own modules
from src.backend.DeckManagement.HelperMethods import *
from src.backend.DeckManagement.ImageHelpers import *
from src.backend.DeckManagement.Subclasses.DeckMediaHandler import DeckMediaHandler

class DeckController:
    key_spacing = (36, 36)
    key_images = None # list with all key images
    background_key_tiles = None # list with all background key image tiles
    background_image = None

    @log.catch
    def __init__(self, deck):
        self.deck = deck
        if not deck.is_open():
            deck.open()
        self.deck.reset()

        self.key_images = [None]*self.deck.key_count() # Fill with None
        self.background_key_tiles = [None]*self.deck.key_count() # Fill with None

        self.media_handler = None
        self.media_handler = DeckMediaHandler(self)

        self.deck.set_key_callback(self.key_change_callback)

    @log.catch
    def generate_key_image(self, image_path=None, image=None, labels=None, image_margins=[0, 0, 0, 0], key=None, add_background=True, shrink=False):
        # margins = [left, top, right, bottom]
        DEFAULT_FONT = "Assets/Fonts/Roboto-Regular.ttf"
        if image != None:
            image = image
        elif image_path != None:
            image = Image.open(image_path)
        else:
            raise Exception("No image provided")
        
        image_height = math.floor(self.deck.key_image_format()["size"][1]-image_margins[1]-image_margins[3])
        image_width = math.floor(self.deck.key_image_format()["size"][0]-image_margins[0]-image_margins[2])

        image = image.resize((image_width, image_height), Image.Resampling.LANCZOS)

        # Generate transparent background to draw everything on
        alpha_bg = Image.new("RGBA", self.deck.key_image_format()["size"], (0, 0, 0, 0))

        # paste image onto background if exists
        if image != None:
            alpha_bg.paste(image, (image_margins[0], image_margins[1]))

        # Add labels
        draw = ImageDraw.Draw(alpha_bg)
        if labels != None:
            # Draw labels onto the image
            for label in list(labels.keys()):
                # Use default font if no font is specified
                if labels[label]["font"] is None:
                    labels[label]["font"] = DEFAULT_FONT
                font = ImageFont.truetype(labels[label]["font"], labels[label]["font-size"])
                # Top text
                if label == "top":
                    draw.text((image.width / 2, labels[label]["font-size"] - 3), text=labels[label]["text"], font=font, anchor="ms",
                              fill=labels[label]["color"], stroke_width=labels[label]["stroke-width"])
                # Center text
                if label == "center":
                    draw.text((image.width / 2, (image.height + labels[label]["font-size"]) / 2 - 3), text=labels[label]["text"], font=font, anchor="ms",
                              fill=labels[label]["color"], stroke_width=labels[label]["stroke-width"])
                # Bottom text
                if label == "bottom":
                    draw.text((image.width / 2, image.height - 3), text=labels[label]["text"], font=font, anchor="ms",
                              fill=labels[label]["color"], stroke_width=labels[label]["stroke-width"])
                    

        if add_background and self.background_key_tiles[key] != None:
            bg = self.background_key_tiles[key].copy() # Load background tile
        else:
            bg = Image.new("RGB", (72, 72), (0, 0, 0)) # Create black background
        bg.paste(alpha_bg, (0, 0), alpha_bg)

        if shrink:
            bg = shrink_image(bg)

        print("returning")
        return PILHelper.to_native_format(self.deck, bg), alpha_bg
    
    @log.catch
    def set_image(self, key, image_path=None, image=None, labels=None, image_margins=[0, 0, 0, 0], add_background=True, bypass_task = False, shrink=False):
        native_image, pillow_image = self.generate_key_image(image_path=image_path, image=image, labels=labels, image_margins=image_margins,
                                            key=key, add_background=add_background, shrink=shrink)
        
        # Set key image
        if bypass_task:
            self.deck.set_key_image(key, native_image)
        else:
            self.media_handler.add_image_task(key, native_image)

        self.key_images[key] = pillow_image
        # self.deck.set_key_image(key, native_image)

    def set_video(self, key, video_path, labels=None, image_margins=[0, 0, 0, 0], add_background=True, loop=True, fps=30):
        self.media_handler.add_video_task(key, video_path, loop=loop, fps=fps)

    def set_background(self, media_path, loop=True, fps=30):
        self.media_handler.set_background(media_path, loop=loop, fps=fps)

    @log.catch
    def reload_keys(self, skip_gifs=True):
        # Stop gif animations to prevent sending conflicts resulting in strange artifacts
        for i in range(self.deck.key_count()):
            if skip_gifs:
                if i in self.media_handler.video_tasks.keys():
                    continue

            image = self.key_images[i]
            bg_image = copy(self.background_key_tiles[i])
            if image == None:
                if bg_image != None:
                    if self.deck.key_states()[i]:
                        # Shrink image
                        bg_image = shrink_image(bg_image) 
                    native_image = PILHelper.to_native_format(self.deck, bg_image)
                    self.media_handler.add_image_task(i, native_image)
                continue
            bg_image.paste(image, (0, 0), image)

            if self.deck.key_states()[i]:
                # Shrink image
                bg_image = shrink_image(bg_image) 

            bg_image = PILHelper.to_native_format(self.deck, bg_image)
            self.media_handler.add_image_task(i, bg_image)

    def key_change_callback(self, deck, key, state):
        self.handle_shrink_animation(deck, key, state)

    @log.catch
    def handle_shrink_animation(self, deck, key, state):
        # Skip if background is animated
        if self.media_handler.background_playing:
            return

        if state:
            self.show_shrinked_image(key)
        else:
            self.show_normal_image(key)
        pass

    @log.catch
    def show_shrinked_image(self, key):
        bg_image = copy(self.background_key_tiles[key])
        image = self.key_images[key]
        if bg_image == None:
            # Theoretically not needed but without it the image gets a weird white outline
            bg_image = Image.new("RGB", (72, 72), (0, 0, 0))
        if image != None:
            bg_image.paste(image, (0, 0), image)
        image = shrink_image(bg_image)

        image_native = PILHelper.to_native_format(self.deck, image)
        self.media_handler.add_image_task(key, image_native)

    @log.catch
    def show_normal_image(self, key):
        bg_image = copy(self.background_key_tiles[key])
        image = self.key_images[key]
        if bg_image == None:
            # Theoretically not needed but without it the image gets a weird white outline
            bg_image = Image.new("RGB", (72, 72), (0, 0, 0))
        if image != None:
            bg_image.paste(image, (0, 0), image)
        image = bg_image.convert("RGB")
        image_native = PILHelper.to_native_format(self.deck, image)
        self.media_handler.add_image_task(key, image_native)



    # Pass deck functions to deck
    def key_count(self):
        return self.deck.key_count()
    
    def set_key_image(self, key, image):
        self.deck.set_key_image(key, image)

    def set_brightness(self, brightness):
        self.deck.set_brightness(brightness)

    def key_state(self, key):
        return self.deck.key_state(key)