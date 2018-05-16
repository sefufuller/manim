import itertools as it
import numpy as np

import aggdraw
import copy
import time
import cairo

from PIL import Image
from colour import Color

from constants import *
from mobject.types.image_mobject import ImageMobject
from mobject.mobject import Mobject
from mobject.types.point_cloud_mobject import PMobject
from mobject.types.vectorized_mobject import VMobject
from utils.color import color_to_int_rgba
from utils.color import rgb_to_hex
from utils.config_ops import digest_config
from utils.images import get_full_raster_image_path
from utils.iterables import batch_by_property
from utils.iterables import list_difference_update
from utils.iterables import remove_list_redundancies
from utils.simple_functions import fdiv


class Camera(object):
    CONFIG = {
        "background_image": None,
        "pixel_shape": (DEFAULT_PIXEL_HEIGHT, DEFAULT_PIXEL_WIDTH),
        # Note: frame_shape will be resized to match pixel_shape
        "frame_shape": (FRAME_HEIGHT, FRAME_WIDTH),
        "space_center": ORIGIN,
        "background_color": BLACK,
        # Points in vectorized mobjects with norm greater
        # than this value will be rescaled.
        "max_allowable_norm": FRAME_WIDTH,
        "image_mode": "RGBA",
        "n_rgb_coords": 4,
        "background_alpha": 0,  # Out of rgb_max_val
        "pixel_array_dtype": 'uint8',
        "use_z_coordinate_for_display_order": False,
        # z_buff_func is only used if the flag above is set to True.
        # round z coordinate to nearest hundredth when comparring
        "z_buff_func": lambda m: np.round(m.get_center()[2], 2),
    }

    def __init__(self, background=None, **kwargs):
        digest_config(self, kwargs, locals())
        self.rgb_max_val = np.iinfo(self.pixel_array_dtype).max

        if RENDERING_ENGINE == "aggdraw":
            self.image_mode = "RGBA"
        elif RENDERING_ENGINE == "cairo":
            self.image_mode = "RGBa" # premultiplied alpha

        self.init_background()
        self.resize_frame_shape()
        self.reset()

    def __deepcopy__(self, memo):
        # This is to address a strange bug where deepcopying
        # will result in a segfault, which is somehow related
        # to the aggdraw library
        self.canvas = None
        return copy.copy(self)

    def resize_frame_shape(self, fixed_dimension=0):
        """
        Changes frame_shape to match the aspect ratio
        of pixel_shape, where fixed_dimension determines
        whether frame_shape[0] (height) or frame_shape[1] (width)
        remains fixed while the other changes accordingly.
        """
        aspect_ratio = float(self.pixel_shape[1]) / self.pixel_shape[0]
        frame_width, frame_height = self.frame_shape
        if fixed_dimension == 0:
            frame_height = aspect_ratio * frame_width
        else:
            frame_width = frame_height / aspect_ratio
        self.frame_shape = (frame_width, frame_height)

    def init_background(self):
        if self.background_image is not None:
            path = get_full_raster_image_path(self.background_image)
<<<<<<< HEAD
            image = Image.open(path).convert("RGBA") #(self.image_mode)
=======
            image = Image.open(path).convert(self.image_mode)
>>>>>>> master
            height, width = self.pixel_shape
            # TODO, how to gracefully handle backgrounds
            # with different sizes?
            self.background = np.array(image)[:height, :width]
            self.background = self.background.astype(self.pixel_array_dtype)
        else:
            background_rgba = color_to_int_rgba(
                self.background_color, alpha=self.background_alpha
            )
            self.background = np.zeros(
                list(self.pixel_shape) + [self.n_rgb_coords],
                dtype=self.pixel_array_dtype
            )
            self.background[:, :] = background_rgba

    def get_image(self):
        if self.image_mode == "RGBA":
            return Image.fromarray(
                self.pixel_array,
                mode=self.image_mode
            )
        elif self.image_mode == "RGBa":
            return Image.fromarray(
                self.unmultiply_alpha(self.pixel_array),
                mode="RGBA"
            )

    def multiply_alpha(self, arr):
        width = arr.shape[0]
        height = arr.shape[1]
        i, j = width/2, height/2
        rgb = arr[:,:,:3]
        alpha = arr[:,:,3]
        extended_dtype = self.get_extended_pixel_array_dtype()
        rgb_ext = rgb.astype(extended_dtype)
        alpha_ext = alpha.astype(extended_dtype)
        rgb_ext = np.where(alpha_ext[:,:,np.newaxis] != 0,
            rgb_ext * alpha_ext[:,:,np.newaxis] / self.rgb_max_val,
            0)
        ret_arr = arr.copy()
        ret_arr[:,:,:3] = rgb_ext.astype(self.pixel_array_dtype)
        return ret_arr

    def unmultiply_alpha(self, arr):
        width = arr.shape[0]
        height = arr.shape[1]
        i, j = width/2, height/2
        rgb = arr[:,:,:3]
        alpha = arr[:,:,3]
        extended_dtype = self.get_extended_pixel_array_dtype()
        rgb_ext = rgb.astype(extended_dtype)
        alpha_ext = alpha.astype(extended_dtype)
        rgb_ext = np.where(alpha_ext[:,:,np.newaxis] != 0,
            rgb_ext * self.rgb_max_val/alpha_ext[:,:,np.newaxis],
            0)
        ret_arr = arr.copy()
        ret_arr[:,:,:3] = rgb_ext.astype(self.pixel_array_dtype)
        return ret_arr


    def get_pixel_array(self):
        return self.pixel_array

    def convert_pixel_array(self, pixel_array, convert_from_floats=False):
        retval = np.array(pixel_array)
        if convert_from_floats:
            retval = np.apply_along_axis(
                lambda f: (
                    f * self.rgb_max_val).astype(self.pixel_array_dtype),
                2,
                retval)
        return retval

    def set_pixel_array(self, pixel_array, convert_from_floats=False):
        converted_array = self.convert_pixel_array(
            pixel_array, convert_from_floats)
        if not (hasattr(self, "pixel_array") and self.pixel_array.shape == converted_array.shape):
            self.pixel_array = converted_array
        else:
            # Set in place
            self.pixel_array[:, :, :] = converted_array[:, :, :]

    def set_background(self, pixel_array, convert_from_floats=False):
        self.background = self.convert_pixel_array(
            pixel_array, convert_from_floats)

    def make_background_from_func(self, coords_to_colors_func):
        """
        Sets background by using coords_to_colors_func to determine each pixel's color. Each input
        to coords_to_colors_func is an (x, y) pair in space (in ordinary space coordinates; not
        pixel coordinates), and each output is expected to be an RGBA array of 4 floats.
        """

        print "Starting set_background; for reference, the current time is ", time.strftime("%H:%M:%S")
        coords = self.get_coords_of_all_pixels()
        new_background = np.apply_along_axis(
            coords_to_colors_func,
            2,
            coords
        )
        print "Ending set_background; for reference, the current time is ", time.strftime("%H:%M:%S")

        return self.convert_pixel_array(new_background, convert_from_floats=True)

    def set_background_from_func(self, coords_to_colors_func):
        self.set_background(
            self.make_background_from_func(coords_to_colors_func))

    def reset(self):
        self.set_pixel_array(self.background)

    ####

    def extract_mobject_family_members(self, mobjects, only_those_with_points=False):
        if only_those_with_points:
            method = Mobject.family_members_with_points
        else:
            method = Mobject.submobject_family
        return remove_list_redundancies(list(
            it.chain(*[
                method(m)
                for m in mobjects
                if not (isinstance(m, VMobject) and m.is_subpath)
            ])
        ))

    def get_mobjects_to_display(
        self, mobjects,
        include_submobjects=True,
        excluded_mobjects=None,
    ):
        if include_submobjects:
            mobjects = self.extract_mobject_family_members(
                mobjects, only_those_with_points=True
            )
            if excluded_mobjects:
                all_excluded = self.extract_mobject_family_members(
                    excluded_mobjects
                )
                mobjects = list_difference_update(mobjects, all_excluded)

        if self.use_z_coordinate_for_display_order:
            # Should perhaps think about what happens here when include_submobjects is False,
            # (for now, the onus is then on the caller to ensure this is handled correctly by
            # passing us an appropriately pre-flattened list of mobjects if need be)
            return sorted(
                mobjects,
                lambda a, b: cmp(self.z_buff_func(a), self.z_buff_func(b))
            )
        else:
            return mobjects

    def capture_mobject(self, mobject, **kwargs):
        return self.capture_mobjects([mobject], **kwargs)

    def capture_mobjects(self, mobjects, **kwargs):
        mobjects = self.get_mobjects_to_display(mobjects, **kwargs)

        # Organize this list into batches of the same type, and
        # apply corresponding function to those batches
        type_func_pairs = [
            (VMobject, self.display_multiple_vectorized_mobjects),
            (PMobject, self.display_multiple_point_cloud_mobjects),
            (ImageMobject, self.display_multiple_image_mobjects),
            (Mobject, lambda batch: batch),  # Do nothing
        ]

        def get_mobject_type(mobject):
            for mobject_type, func in type_func_pairs:
                if isinstance(mobject, mobject_type):
                    return mobject_type
            raise Exception(
                "Trying to display something which is not of type Mobject"
            )
        batch_type_pairs = batch_by_property(mobjects, get_mobject_type)

        # Display in these batches
        for batch, batch_type in batch_type_pairs:
            # check what the type is, and call the appropriate function
            for mobject_type, func in type_func_pairs:
                if batch_type == mobject_type:
                    func(batch)

    # Methods associated with svg rendering

    def get_aggdraw_canvas(self):
        if not hasattr(self, "canvas") or not self.canvas:
            self.reset_aggdraw_canvas()
        return self.canvas

    def reset_aggdraw_canvas(self):
        image = Image.fromarray(self.pixel_array, mode=self.image_mode)
        self.canvas = aggdraw.Draw(image)

    def get_cairo_context(self):
        if not hasattr(self, "context") or not self.context:
            self.reset_cairo_context()
        return self.context

    def reset_cairo_context(self):
        width = self.pixel_shape[0]
        height = self.pixel_shape[1]
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, height, width)
        self.context = cairo.Context(self.surface)


    def display_multiple_vectorized_mobjects(self, vmobjects):
        if len(vmobjects) == 0:
            return
        batch_file_pairs = batch_by_property(
            vmobjects,
            lambda vm: vm.get_background_image_file()
        )
        for batch, file_name in batch_file_pairs:
            if file_name:
                self.display_multiple_background_colored_vmobject(batch)
            else:
                self.display_multiple_non_background_colored_vmobjects(batch)

    def display_multiple_non_background_colored_vmobjects(self, vmobjects):
        width = self.pixel_shape[0]
        height = self.pixel_shape[1]
        canvas, context = None, None
        if RENDERING_ENGINE == "aggdraw":
            self.reset_aggdraw_canvas()
            canvas = self.get_aggdraw_canvas()
        elif RENDERING_ENGINE == "cairo":
            self.reset_cairo_context()
            context = self.get_cairo_context()
        for (i,vmobject) in enumerate(vmobjects):
            self.display_vectorized(vmobject, canvas, context)
        if RENDERING_ENGINE == "aggdraw":
            canvas.flush()
        elif RENDERING_ENGINE == "cairo":
            buf = self.surface.get_data()
            width = self.pixel_shape[0]
            height = self.pixel_shape[1]
            np_buf = np.ndarray(shape=(width, height, 4),
                     dtype=self.pixel_array_dtype,
                     buffer=buf)
            np_buf[:,:,:3] = np_buf[:,:,2::-1] # buf is BGRA for some reason
            i, j = width/2, height/2
            self.overlay_rgba_array(np_buf, premultiplied = True)
            

    def display_vectorized(self, vmobject, canvas=None, context=None):
        if canvas == None and context == None:
            raise Exception("canvas and context cannot be both None")

        if vmobject.is_subpath:
            # Subpath vectorized mobjects are taken care
            # of by their parent
            return

        if RENDERING_ENGINE == "aggdraw":

            canvas = canvas or self.get_aggdraw_canvas()
            pen, fill = self.get_pen_and_fill(vmobject)
            pathstring = self.get_pathstring(vmobject)
            symbol = aggdraw.Symbol(pathstring)
            canvas.symbol((0, 0), symbol, pen, fill)

        elif RENDERING_ENGINE == "cairo":
            context = self.write_path_to_context(context, vmobject)
            fill_rgba = self.get_fill_rgba(vmobject)
            context.set_source_rgba(*fill_rgba)
            context.fill()
            context = self.write_path_to_context(context, vmobject)
            context.set_source_rgb(*self.get_stroke_rgb(vmobject))
            context.set_line_width(max(vmobject.get_stroke_width(),0))
            context.stroke()




    def write_path_to_context(self, context, vmobject):
        context = context or self.get_cairo_context()
        path_array = self.get_path_array(vmobject)
        for curve_array in path_array:
            context.move_to(*curve_array[0])
            for bezier_array in curve_array[1:]:
                if bezier_array == "close":
                    context.close_path()
                    break
                context.curve_to(*bezier_array)
        return context

    def convert_path_string_to_array(self, path_string):
        bezier_strings = path_string.split("M")[1:]
        path_array = []
        for string in bezier_strings:
            close_path = False
            if string[-1] == "Z":
                close_path = True
                string = string[:-2]
            curve_strings = string.split("C")
            start_point_string = curve_strings[0]
            curve_array = [self.convert_string_to_int_array(start_point_string)]
            curve_array += [
                self.convert_string_to_int_array(bezier_string)
                for bezier_string in curve_strings[1:]
            ]
            if close_path:
                curve_array.append("close")

            path_array.append(curve_array)

        return path_array


    def convert_string_to_int_array(self, string):
        substrings = string.split(" ")
        if substrings[-1] == "":
            substrings = substrings[:-1]
        return [int(substr) for substr in substrings]

    def get_path_array(self, vmobject):
        pathstring = self.get_pathstring(vmobject)
        return self.convert_path_string_to_array(pathstring)


    def get_pen_and_fill(self, vmobject):
        stroke_width = max(vmobject.get_stroke_width(), 0)
        if stroke_width == 0:
            pen = None
        else:
            stroke_rgb = self.get_stroke_rgb(vmobject)
            stroke_hex = rgb_to_hex(stroke_rgb)
            pen = aggdraw.Pen(stroke_hex, stroke_width)

        fill_opacity = int(self.rgb_max_val * vmobject.get_fill_opacity())
        if fill_opacity == 0:
            fill = None
        else:
            fill_rgb = self.get_fill_rgb(vmobject)
            fill_hex = rgb_to_hex(fill_rgb)
            fill = aggdraw.Brush(fill_hex, fill_opacity)

        return (pen, fill)

    def color_to_hex_l(self, color):
        try:
            return color.get_hex_l()
        except:
            return Color(BLACK).get_hex_l()

    def get_stroke_rgb(self, vmobject):
        return vmobject.get_stroke_rgb()

    def get_fill_rgb(self, vmobject):
        return vmobject.get_fill_rgb()

    def get_stroke_rgba(self, vmobject):
        return vmobject.get_stroke_rgba()

    def get_fill_rgba(self, vmobject):
        return vmobject.get_fill_rgba()

    def get_pathstring(self, vmobject):
        result = ""
        for mob in [vmobject] + vmobject.get_subpath_mobjects():
            points = mob.points
            # points = self.adjust_out_of_range_points(points)
            if len(points) == 0:
                continue
            aligned_points = self.align_points_to_camera(points)
            coords = self.points_to_pixel_coords(aligned_points)
            coord_strings = coords.flatten().astype(str)
            # Start new path string with M
            coord_strings[0] = "M" + coord_strings[0]
            # The C at the start of every 6th number communicates
            # that the following 6 define a cubic Bezier
            coord_strings[2::6] = map(
                lambda s: "C" + str(s), coord_strings[2::6])
            # Possibly finish with "Z"
            if vmobject.mark_paths_closed:
                coord_strings[-1] = coord_strings[-1] + " Z"
            result += " ".join(coord_strings)
        return result



    def get_background_colored_vmobject_displayer(self):
        # Quite wordy to type out a bunch
        long_name = "background_colored_vmobject_displayer"
        if not hasattr(self, long_name):
            setattr(self, long_name, BackgroundColoredVMobjectDisplayer(self))
        return getattr(self, long_name)

    def display_multiple_background_colored_vmobject(self, cvmobjects):
        displayer = self.get_background_colored_vmobject_displayer()
        cvmobject_pixel_array = displayer.display(*cvmobjects)
        self.overlay_rgba_array(cvmobject_pixel_array)
        return self

    # Methods for other rendering

    def display_multiple_point_cloud_mobjects(self, pmobjects):
        for pmobject in pmobjects:
            self.display_point_cloud(
                pmobject.points,
                pmobject.rgbas,
                self.adjusted_thickness(pmobject.stroke_width)
            )

    def display_point_cloud(self, points, rgbas, thickness):
        if len(points) == 0:
            return
        points = self.align_points_to_camera(points)
        pixel_coords = self.points_to_pixel_coords(points)
        pixel_coords = self.thickened_coordinates(
            pixel_coords, thickness
        )
        rgba_len = self.pixel_array.shape[2]

        rgbas = (self.rgb_max_val * rgbas).astype(self.pixel_array_dtype)
        target_len = len(pixel_coords)
        factor = target_len / len(rgbas)
        rgbas = np.array([rgbas] * factor).reshape((target_len, rgba_len))

        on_screen_indices = self.on_screen_pixels(pixel_coords)
        pixel_coords = pixel_coords[on_screen_indices]
        rgbas = rgbas[on_screen_indices]

        ph, pw = self.pixel_shape

        flattener = np.array([1, pw], dtype='int')
        flattener = flattener.reshape((2, 1))
        indices = np.dot(pixel_coords, flattener)[:, 0]
        indices = indices.astype('int')

        new_pa = self.pixel_array.reshape((ph * pw, rgba_len))
        new_pa[indices] = rgbas
        self.pixel_array = new_pa.reshape((ph, pw, rgba_len))

    def display_multiple_image_mobjects(self, image_mobjects):
        for image_mobject in image_mobjects:
            self.display_image_mobject(image_mobject)

    def display_image_mobject(self, image_mobject):
        corner_coords = self.points_to_pixel_coords(image_mobject.points)
        ul_coords, ur_coords, dl_coords = corner_coords
        right_vect = ur_coords - ul_coords
        down_vect = dl_coords - ul_coords

        impa = image_mobject.pixel_array

        oh, ow = self.pixel_array.shape[:2]  # Outer width and height
<<<<<<< HEAD
        ih, iw = impa.shape[:2]  # inner width and height
=======
        ih, iw = impa.shape[:2]  # inner with and height
>>>>>>> master
        rgb_len = self.pixel_array.shape[2]

        image = np.zeros((oh, ow, rgb_len), dtype=self.pixel_array_dtype)

        if right_vect[1] == 0 and down_vect[0] == 0:
            rv0 = right_vect[0]
            dv1 = down_vect[1]
            x_indices = np.arange(rv0, dtype='int') * iw / rv0
            y_indices = np.arange(dv1, dtype='int') * ih / dv1
            stretched_impa = impa[y_indices][:, x_indices]

            x0, x1 = ul_coords[0], ur_coords[0]
            y0, y1 = ul_coords[1], dl_coords[1]
            if x0 >= ow or x1 < 0 or y0 >= oh or y1 < 0:
                return
            siy0 = max(-y0, 0)  # stretched_impa y0
            siy1 = dv1 - max(y1 - oh, 0)
            six0 = max(-x0, 0)
            six1 = rv0 - max(x1 - ow, 0)
            x0 = max(x0, 0)
            y0 = max(y0, 0)
            image[y0:y1, x0:x1] = stretched_impa[siy0:siy1, six0:six1]
        else:
            # Alternate (slower) tactic if image is tilted
            # List of all coordinates of pixels, given as (x, y),
            # which matches the return type of points_to_pixel_coords,
            # even though np.array indexing naturally happens as (y, x)
            all_pixel_coords = np.zeros((oh * ow, 2), dtype='int')
            a = np.arange(oh * ow, dtype='int')
            all_pixel_coords[:, 0] = a % ow
            all_pixel_coords[:, 1] = a / ow

            recentered_coords = all_pixel_coords - ul_coords

            with np.errstate(divide='ignore'):
                ix_coords, iy_coords = [
                    np.divide(
                        dim * np.dot(recentered_coords, vect),
                        np.dot(vect, vect),
                    )
                    for vect, dim in (right_vect, iw), (down_vect, ih)
                ]
            to_change = reduce(op.and_, [
                ix_coords >= 0, ix_coords < iw,
                iy_coords >= 0, iy_coords < ih,
            ])
            inner_flat_coords = iw * \
                iy_coords[to_change] + ix_coords[to_change]
            flat_impa = impa.reshape((iw * ih, rgb_len))
            target_rgbas = flat_impa[inner_flat_coords, :]

            image = image.reshape((ow * oh, rgb_len))
            image[to_change] = target_rgbas
            image = image.reshape((oh, ow, rgb_len))
<<<<<<< HEAD

        if self.image_mode == "RGBA":
            self.overlay_rgba_array(image, premultiplied = False)
        elif self.image_mode == "RGBa":
            self.overlay_rgba_array(self.multiply_alpha(image), premultiplied = True)



    def old_overlay_rgba_array(self, arr):

        width = self.pixel_array.shape[0]
        height = self.pixel_array.shape[1]
        fg = arr
        bg = self.pixel_array
        # rgba_max_val = self.rgb_max_val
        src_rgb, src_a, dst_rgb, dst_a = [
            a.astype(np.float32) / self.rgb_max_val
            for a in fg[..., :3], fg[..., 3], bg[..., :3], bg[..., 3]
        ]

        out_a = src_a + dst_a * (1.0 - src_a)

        # When the output alpha is 0 for full transparency,
        # we have a choice over what RGB value to use in our
        # output representation. We choose 0 here.
        out_rgb = fdiv(
            src_rgb * src_a[..., None] +
            dst_rgb * dst_a[..., None] * (1.0 - src_a[..., None]),
            out_a[..., None],
            zero_over_zero_value=0
        )
=======
        self.overlay_rgba_array(image)

    def overlay_rgba_array(self, arr):
        fg = arr
        bg = self.pixel_array
        # rgba_max_val = self.rgb_max_val
        src_rgb, src_a, dst_rgb, dst_a = [
            a.astype(np.float32) / self.rgb_max_val
            for a in fg[..., :3], fg[..., 3], bg[..., :3], bg[..., 3]
        ]

        out_a = src_a + dst_a * (1.0 - src_a)

        # When the output alpha is 0 for full transparency,
        # we have a choice over what RGB value to use in our
        # output representation. We choose 0 here.
        out_rgb = fdiv(
            src_rgb * src_a[..., None] +
            dst_rgb * dst_a[..., None] * (1.0 - src_a[..., None]),
            out_a[..., None],
            zero_over_zero_value=0
        )

        self.pixel_array[..., :3] = out_rgb * self.rgb_max_val
        self.pixel_array[..., 3] = out_a * self.rgb_max_val

    def align_points_to_camera(self, points):
        # This is where projection should live
        return points - self.space_center
>>>>>>> master

        self.pixel_array[..., :3] = out_rgb * self.rgb_max_val
        self.pixel_array[..., 3] = out_a * self.rgb_max_val
        

    def get_extended_pixel_array_dtype(self):
        dtype_converter = {
            "uint8" : "uint16",
            "uint16" : "uint32",
            "uint32" : "uint64"
        }
        return dtype_converter[self.pixel_array_dtype]


    def overlay_rgba_array(self, arr, premultiplied = False):

        width = arr.shape[0]
        height = arr.shape[1]
        i, j = width/2, height/2
        
        extended_dtype = self.get_extended_pixel_array_dtype()

        width = self.pixel_array.shape[0]
        height = self.pixel_array.shape[1]
        i,j = width/2, height/2
        fg = arr
        bg = self.pixel_array
        src_rgb, src_a = fg[..., :3], fg[..., 3]
        dst_rgb, dst_a = bg[..., :3], bg[..., 3]

        src_a_ext = src_a.astype(extended_dtype)
        dst_a_ext = dst_a.astype(extended_dtype)
        a1_ext = dst_a_ext
        a1_ext *= (self.rgb_max_val - src_a_ext)
        a1_ext /= self.rgb_max_val
        
        out_a_ext = src_a_ext + a1_ext
        out_a = out_a_ext.astype(self.pixel_array_dtype)

        src_rgb_ext = src_rgb.astype(extended_dtype)
        dst_rgb_ext = dst_rgb.astype(extended_dtype)

        if premultiplied:
            
            rgb1_ext = dst_rgb_ext
            rgb1_ext *= (self.rgb_max_val - src_a_ext[:,:,np.newaxis])
            out_rgb_ext = src_rgb_ext * self.rgb_max_val + rgb1_ext
            out_rgb_ext /= self.rgb_max_val
            
        else:

            rgb1_ext = dst_rgb_ext * dst_a_ext[:,:,np.newaxis] / self.rgb_max_val
            rgb1_ext *= (self.rgb_max_val - src_a_ext[:,:,np.newaxis])
            out_rgb_ext = np.where(out_a_ext[:,:,np.newaxis] != 0,
            (src_rgb_ext * src_a_ext[:,:,np.newaxis] + rgb1_ext) / out_a_ext[:,:,np.newaxis], 
            0)

        out_rgb = out_rgb_ext.astype(self.pixel_array_dtype)

        self.pixel_array[..., :3] = out_rgb
        self.pixel_array[..., 3] = out_a



    def align_points_to_camera(self, points):
        # This is where projection should live
        return points - self.space_center

    def adjust_out_of_range_points(self, points):
        if not np.any(points > self.max_allowable_norm):
            return points
        norms = np.apply_along_axis(np.linalg.norm, 1, points)
        violator_indices = norms > self.max_allowable_norm
        violators = points[violator_indices, :]
        violator_norms = norms[violator_indices]
        reshaped_norms = np.repeat(
            violator_norms.reshape((len(violator_norms), 1)),
            points.shape[1], 1
        )
        rescaled = self.max_allowable_norm * violators / reshaped_norms
        points[violator_indices] = rescaled
        return points

    def points_to_pixel_coords(self, points):
        result = np.zeros((len(points), 2))
        ph, pw = self.pixel_shape
        sh, sw = self.frame_shape
        width_mult = pw / sw
        width_add = pw / 2
        height_mult = ph / sh
        height_add = ph / 2
        # Flip on y-axis as you go
        height_mult *= -1

        result[:, 0] = points[:, 0] * width_mult + width_add
        result[:, 1] = points[:, 1] * height_mult + height_add
        return result.astype('int')

    def on_screen_pixels(self, pixel_coords):
        return reduce(op.and_, [
            pixel_coords[:, 0] >= 0,
            pixel_coords[:, 0] < self.pixel_shape[1],
            pixel_coords[:, 1] >= 0,
            pixel_coords[:, 1] < self.pixel_shape[0],
        ])

    def adjusted_thickness(self, thickness):
        big_shape = PRODUCTION_QUALITY_CAMERA_CONFIG["pixel_shape"]
        factor = sum(big_shape) / sum(self.pixel_shape)
        return 1 + (thickness - 1) / factor

    def get_thickening_nudges(self, thickness):
        _range = range(-thickness / 2 + 1, thickness / 2 + 1)
        return np.array(list(it.product(_range, _range)))

    def thickened_coordinates(self, pixel_coords, thickness):
        nudges = self.get_thickening_nudges(thickness)
        pixel_coords = np.array([
            pixel_coords + nudge
            for nudge in nudges
        ])
        size = pixel_coords.size
        return pixel_coords.reshape((size / 2, 2))

    def get_coords_of_all_pixels(self):
        # These are in x, y order, to help me keep things straight
        full_space_dims = np.array(self.frame_shape)[::-1]
        full_pixel_dims = np.array(self.pixel_shape)[::-1]

        # These are addressed in the same y, x order as in pixel_array, but the values in them
        # are listed in x, y order
        uncentered_pixel_coords = np.indices(self.pixel_shape)[
            ::-1].transpose(1, 2, 0)
        uncentered_space_coords = fdiv(
            uncentered_pixel_coords * full_space_dims,
            full_pixel_dims)
        # Could structure above line's computation slightly differently, but figured (without much
        # thought) multiplying by frame_shape first, THEN dividing by pixel_shape, is probably
        # better than the other order, for avoiding underflow quantization in the division (whereas
        # overflow is unlikely to be a problem)

        centered_space_coords = (
            uncentered_space_coords - fdiv(full_space_dims, 2))

        # Have to also flip the y coordinates to account for pixel array being listed in
        # top-to-bottom order, opposite of screen coordinate convention
        centered_space_coords = centered_space_coords * (1, -1)

        return centered_space_coords


class BackgroundColoredVMobjectDisplayer(object):
    def __init__(self, camera):
        self.camera = camera
        self.file_name_to_pixel_array_map = {}
        self.init_canvas()

    def init_canvas(self):
        self.pixel_array = np.zeros(
            self.camera.pixel_array.shape,
            dtype=self.camera.pixel_array_dtype,
        )
        self.reset_canvas()

    def reset_canvas(self):
        image = Image.fromarray(self.pixel_array, mode=self.camera.image_mode)
        self.canvas = aggdraw.Draw(image)

    def resize_background_array(
        self, background_array,
        new_width, new_height,
        mode="RGBA"
    ):
        image = Image.fromarray(background_array, mode=mode)
        resized_image = image.resize((new_width, new_height))
        return np.array(resized_image)

    def resize_background_array_to_match(self, background_array, pixel_array):
        height, width = pixel_array.shape[:2]
        mode = "RGBA" if pixel_array.shape[2] == 4 else "RGB"
        return self.resize_background_array(background_array, width, height, mode)

    def get_background_array(self, file_name):
        if file_name in self.file_name_to_pixel_array_map:
            return self.file_name_to_pixel_array_map[file_name]
        full_path = get_full_raster_image_path(file_name)
        image = Image.open(full_path)
        array = np.array(image)

        camera = self.camera
        if not np.all(camera.pixel_array.shape == array.shape):
            array = self.resize_background_array_to_match(
                array, camera.pixel_array)

        self.file_name_to_pixel_array_map[file_name] = array
        return array

    def display(self, *cvmobjects):
        batch_image_file_pairs = batch_by_property(
            cvmobjects, lambda cv: cv.get_background_image_file()
        )
        curr_array = None
        for batch, image_file in batch_image_file_pairs:
            background_array = self.get_background_array(image_file)
            for cvmobject in batch:
                self.camera.display_vectorized(cvmobject, self.canvas)
            self.canvas.flush()
            new_array = np.array(
                (background_array * self.pixel_array.astype('float') / 255),
                dtype=self.camera.pixel_array_dtype
            )
            if curr_array is None:
                curr_array = new_array
            else:
                curr_array = np.maximum(curr_array, new_array)
            self.pixel_array[:, :] = 0
            self.reset_canvas()
        return curr_array
