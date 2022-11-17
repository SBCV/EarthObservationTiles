class BoundedArea:
    def get_bounds_crs(self, dst_crs):
        raise NotImplementedError

    def get_left_top_bound_corner(self, dst_crs=None):
        # BoundingBox(left, bottom, right, top)
        l, b, r, t = self.get_bounds_crs(dst_crs)
        return l, t

    def get_right_top_bound_corner(self, dst_crs=None):
        # BoundingBox(left, bottom, right, top)
        l, b, r, t = self.get_bounds_crs(dst_crs)
        return r, t

    def get_left_bottom_bound_corner(self, dst_crs=None):
        # BoundingBox(left, bottom, right, top)
        l, b, r, t = self.get_bounds_crs(dst_crs)
        return l, b

    def get_right_bottom_bound_corner(self, dst_crs=None):
        l, b, r, t = self.get_bounds_crs(dst_crs)
        return r, b
