import sys


class Package:
    """Represents a package in a repository"""

    def __init__(self, name, repo):
        self.name = name
        self.repo = repo  # Reference back to the repository

    def __repr__(self):
        return f"Package('{self.name}', repo={self.repo.url})"


class Repository:
    """Base repository class"""

    def __init__(self, url):
        self.url = url
        self._packages = []

    def __call__(self, *package_list):
        """Make repository callable to create package lists"""
        # if isinstance(package_list, str):
        #     package_list = [package_list]
        result = []
        # Handle both Python lists and Lua tables
        # Lua tables from lupa need to be accessed by their integer keys
        try:
            # Try to iterate as a Python iterable first
            items = list(package_list)
            # Check if we got Lua table indices (integers) instead of values
            if items and isinstance(items[0], int):
                # This is a Lua table, access values by index
                items = [package_list[i] for i in items]
        except (TypeError, AttributeError):
            # If that fails, try to access as a Lua table with integer indices
            items = []
            i = 1
            while True:
                try:
                    item = package_list[i]
                    if item is None:
                        break
                    items.append(item)
                    i += 1
                except (KeyError, IndexError):
                    break

        for pkg_name in items:
            pkg = Package(pkg_name, self)
            result.append(pkg)
            self._packages.append(pkg)
        return PackageList(result)

    def __repr__(self):
        return f"{self.__class__.__name__}('{self.url}')"


class PackageList:
    """List of packages with concatenation support"""

    def __init__(self, packages=None):
        self.packages = packages or []

    def __add__(self, other):
        """Implement + operator"""
        if isinstance(other, PackageList):
            combined = PackageList(self.packages + other.packages)
            return combined
        raise TypeError(f"Cannot add {type(other)} to PackageList")

    def __radd__(self, other):
        """Implement right-hand + operator"""
        return self.__add__(other)

    def __concat__(self, other):
        """Implement Lua .. concatenation operator"""
        return self.__add__(other)

    def __iadd__(self, other):
        """Implement += operator"""
        if isinstance(other, PackageList):
            self.packages.extend(other.packages)
            return self
        raise TypeError(f"Cannot add {type(other)} to PackageList")

    def __iter__(self):
        """Make PackageList iterable"""
        return iter(self.packages)

    def __getitem__(self, index):
        """Make PackageList indexable"""
        return self.packages[index]

    def __len__(self):
        """Support len()"""
        return len(self.packages)

    def __repr__(self):
        return f"PackageList({self.packages})"


class Arch(Repository):
    """Arch Linux official repository"""

    def __init__(self, url="https://archlinux.org/packages/"):
        super().__init__(url)


class AUR(Repository):
    """Arch User Repository"""

    def __init__(self, cmd, url="https://aur.archlinux.org/"):
        super().__init__(url)
        self.command = cmd


class Flatpak(Repository):
    """Flatpak Repository"""

    def __init__(self, url="flathub"):
        super().__init__(url)
