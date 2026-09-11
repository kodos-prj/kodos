-- Eszkoz configuration adapted for Phase 5d structured schema
-- This version uses the new nested blocks structure:
--   - users.abuss.identity (name, hashed_password, groups)
--   - users.abuss.ssh_keys (authorized keys)
--   - users.abuss.dotfiles (repo configuration)
--   - users.abuss.programs and users.abuss.services (nested)
--   - desktop.display_manager and desktop.environments

print("Eszkoz configuration (Phase 5d adapted)")

local disk = require("disk")
local repos = require("repos")
local configs = require("configs")
local themes = require("modules/themes")

-- Extra packages
local cli = require("cli")
local development = require("development")
local extra = require("extra")

local use_gnome = true
local use_plasma = false
local use_cosmic = true
local use_pantheon = false
local use_budgie = false
local use_xfce = false

return {
	base_distribution = "arch",
	repos = {
		official = repos.arch_repo("https://mirror.rackspace.com/archlinux"),
		aur = repos.aur_repo("yay", "https://aur.archlinux.org/yay-bin.git"),
		flatpak = repos.flatpak_repo("flathub"),
	},

	devices = {
		disk0 = disk.disk_definition("/dev/nvme0n1", "34GB"),
	},

	boot = {
		kernel = {
			package = "linux",
			modules = { "xhci_pci", "ohci_pci", "ehci_pci", "virtio_pci", "ahci", "usbhid", "sr_mod", "virtio_blk" },
		},
		loader = {
			type = "systemd-boot",
			timeout = 10,
			include = { "memtest86+" },
		},
	},

	hardware = {
		sane = {
			enable = true,
			extra_packages = { "sane-airscan" },
		},

		pipewire = {
			enable = true,
			extra_packages = {
				"pipewire-alsa",
				"pipewire-pulse",
			},
		},
	},

	locale = {
		locale = {
			default = "en_CA.UTF-8 UTF-8",
			extra_generate = {
				"en_US.UTF-8 UTF-8",
				"en_GB.UTF-8 UTF-8",
			},
			extra_settings = {
				LC_ADDRESS = "en_CA.UTF-8",
				LC_IDENTIFICATION = "en_CA.UTF-8",
				LC_MEASUREMENT = "en_CA.UTF-8",
				LC_MONETARY = "en_CA.UTF-8",
				LC_NAME = "en_CA.UTF-8",
				LC_NUMERIC = "en_CA.UTF-8",
				LC_PAPER = "en_CA.UTF-8",
				LC_TELEPHONE = "en_CA.UTF-8",
				LC_TIME = "en_CA.UTF-8",
			},
		},
		keymap = "us",
		timezone = "America/Edmonton",
	},

	network = {
		hostname = "eszkoz",
		ipv6 = false,
	},

	users = {

		root = {
			shell = "/bin/bash",
			identity = {
				hashed_password = nil,  -- root has no password
			}
		},

		abuss = {
			-- Phase 5d: User identity moved to identity block
			identity = {
				name = "Antal Buss",
				hashed_password = "$6$MOkGLOzXlj0lIE2d$5sxAysiDyD/7ZfntgZaN3vJ48t.BMi2qwPxqjgVxGXKXrNlFxRvnO8uCvOlHaGW2pVDrjt0JLNR9GWH.2YT5j.",
				groups = { "audio", "input", "users", "video", "wheel" },
			},

			shell = "/usr/bin/zsh",

			-- Phase 5d: SSH keys moved to ssh_keys block
			ssh_keys = {
				enabled = true,
				authorized = {
					"ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDOA6V+TZJ+BmBAU4FB0nbhYQ9XOFZwCHdwXTuQkb77sPi6fVcbzso5AofUc+3DhfN56ATNOOslvjutSPE8kIp3Uv91/c7DE0RHoidNl3oLre8bau2FT+9AUTZnNEtWH/qXp5+fzvGk417mSL3M5jdoRwude+AzhPNXmbdAzn08TMGAkjGrMQejXItcG1OhXKUjqeLmB0A0l3Ac8DGQ6EcSRtgPCiej8Boabn21K2OBfq64KwW/MMh/FWTHndyBF/lhfEos7tGPvrDN+5G05oGjf0fnMOxsmAUdTDbtOTTeMTvDwjJdzsGUluEDbWBYPNlg5wacbimkv51/Bm4YwsGOkkUTy6eCCS3d5j8PrMbB2oNZfByga01FohhWSX9bv35KAP4nq7no9M6nXj8rQVsF0gPndPK/pgX46tpJG+pE1Ul6sSLR2jnrN6oBKzhdZJ54a2wwFSd207Zvahdx3m9JEVhccmDxWltxjKHz+zChAHsqWC9Zcqozt0mDRJNalW8fRXKcSWPGVy1rfbwltiQzij+ChCQQlUG78zW8lU7Bz6FuyDsEFpZSat7jtbdDBY0a4F0yb4lkNvu+5heg+dhlKCFj9YeRDrnvcz94OKvAZW1Gsjbs83n6wphBipxUWku7y86iYyAAYQGKs4jihhYWrFtfZhSf1m6EUKXoWX87KQ== antal.buss@gmail.com",
				},
			},

			-- Phase 5d: Dotfiles moved to dotfiles block
			dotfiles = {
				source_dir = "~/.dotfiles",
				repo_url = "http://git.homecloud.lan/abuss/dotconfig.git",
				deploy_tool = "stow",
			},

			-- Phase 5d: User programs (now supported at user level)
			programs = {
				git = {
					enable = true,
					config = configs.git({
						user_name = "Antal Buss",
						user_email = "antal.buss@gmail.com",
						core_editor = "helix",
					}),
				},

				starship = {
					enable = true,
					deploy_config = true,
				},

				fish = {
					enable = true,
				},

				zsh = {
					enable = true,
					deploy_config = true,
				},

				neovim = {
					enable = true,
					deploy_config = true,
				},

				helix = {
					enable = true,
					deploy_config = true,
				},

				emacs = {
					enable = true,
					package = "emacs-wayland",
					deploy_config = true,
					extra_packages = { "aspell", "aspell-en" },
				},

				-- Gnome dconf configuration
				dconf = {
					enable = use_gnome,
					config = configs.dconf(require("gnome")),
				},
			},

			-- Phase 5d: User services (now supported at user level)
			services = {
				syncthing = {
					enable = false,
					config = configs.syncthing({
						service_name = "syncthing",
						options = "'--no-browser' '--no-restart' '--logflags=0' '--gui-address=0.0.0.0:8384'",
					}),
				},
			},

			home_config = {
				dotfiles_repos = {
					"http://git.homecloud.lan/abuss/dotconfig.git",
				},
			},
		},
	},

	desktop = {
		-- Phase 5d: display_manager is now a top-level field
		display_manager = "cosmic-greeter",
		
		-- Phase 5d: desktop_manager moved to environments block
		environments = {
			gnome = {
				enable = use_gnome,
				exclude_packages = {
					"gnome-tour",
					"yelp",
				},
				extra_packages = {
					"gnome-tweaks",
					"showtime",
					"gnome-connections",
					"gnome-shell-extension-appindicator",
					"aur:gnome-shell-extension-dash-to-dock",
					"aur:gnome-shell-extension-blur-my-shell",
					"aur:gnome-shell-extension-arc-menu-git",
					"aur:gnome-shell-extension-gsconnect",
					"gnome-shell-extension-weather-oclock",
					"flatpak:com.mattjakeman.ExtensionManager",
				},
			},

			plasma = {
				enable = use_plasma,
				display_manager = "sddm",
				extra_packages = {
					"kde-applications",
					"kvantum",
					"aur:plasma6-theme-mcmojave-git",
				},
			},

			cosmic = {
				enable = use_cosmic,
				display_manager = "cosmic-greeter",
			},

			budgie = {
				enable = use_budgie,
				display_manager = "lightdm",
				extra_packages = {
					"lightdm-gtk-greeter",
					"network-manager-applet",
				},
			},
			pantheon = {
				enable = use_pantheon,
				display_manager = "gdm",
			},
		},
	},

	fonts = {
		font_dir = true,
		packages = {
			"ttf-firacode-nerd",
			"ttf-nerd-fonts-symbols",
			"ttf-nerd-fonts-symbols-common",
			"ttf-sourcecodepro-nerd",
			"ttf-fira-sans",
			"ttf-fira-code",
			"ttf-liberation",
			"noto-fonts-emoji",
			"adobe-source-serif-fonts",
			"ttf-ubuntu-font-family",
		},
	},

	packages = list({
		"iw",
		"stow",
		"mc",
		"less",
		"neovim",
		"htop",
		"libgtop",
		"power-profiles-daemon",
		"system-config-printer",
		"git",
		"ghostty",
		"aur:visual-studio-code-bin",
		"distrobox",
		"podman",
		"podman-compose",
		"podman-docker",
		"aur:quickemu",
		"qemu-desktop",
		"libvirt",
		"dnsmasq",
		"spice-gtk",
		"aur:uxplay",
		"aur:megasync-bin",
		"remmina",
		"papers",

		"firefox",
		"aur:brave-bin",
		"vivaldi",
		"vivaldi-ffmpeg-codecs",
		"openssh",
	})
		.. cli
		.. development
		.. extra,

	services = {
		-- Firmware update
		fwupd = { enable = true },

		tailscale = { enable = true },

		networkmanager = {
			enable = true,
			service_name = "NetworkManager",
		},

		nix = {
			enable = false,
			service_name = "nix_daemon",
		},

		openssh = {
			enable = true,
			service_name = "sshd",
			settings = {
				PermitRootLogin = false,
			},
		},

		avahi = {
			enable = true,
		},

		cups = {
			enable = true,
			extra_packages = { "gutenprint", "aur:brother-dcp-l2550dw" },
		},

		bluetooth = {
			enable = true,
			service_name = "bluetooth",
			package = "bluez",
		},

		-- Phase 5d: systemd block supports mounts and units
		systemd = {
			enable = false,

			mounts = {
				data = {
					type = "cifs",
					what = "//mmserver.lan/NAS1",
					where = "/mnt/data",
					description = "MMserverNAS1",
					options = "vers=2.1,credentials=/etc/samba/mmserver-cred,iocharset=utf8,rw,x-systemd.automount,uid=1000",
					after = "network.target",
					wanted_by = "multi-user.target",
					automount = true,
					automount_config = "TimeoutIdleSec=0",
				},

				library = {
					type = "nfs",
					what = "homenas2.lan:/data/Documents",
					where = "/mnt/library/",
					description = "Document library",
					options = "noatime,x-systemd.automount,noauto",
					after = "network.target",
					wanted_by = "multi-user.target",
					automount = true,
					automount_config = "TimeoutIdleSec=600",
				},
			},
		},
	},
}
