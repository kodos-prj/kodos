-- Disk partition definition

return  {
   device = "/dev/vda",
   efi = true,
   -- efi_size = 1024,
   type = "gpt",
   filesystem = "ext4",
   partitions = {
      {
         name = "Boot",
         size = "1GB",
         type = "fat32",
         mountpoint = "/boot",
      },
      {
         name = "Swap",
         size = "3GB",
         type = "linux-swap",
         resumeDevice = true,
      },
      {
         name = "Root",
         size = "100%",
         type = "ext4",
         mountpoint = "/",
      },
   },
}
