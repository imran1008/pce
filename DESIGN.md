# Design
This document describes some of the design decisions of PCE.

## Filesystem: BTRFS
Btrfs and ZFS are next generation copy-on-write filesystem that provide many features to ensure data integrity. Both
are great filesystems, provide measures to prevent data corruption (include bit-rot corruption). There are a few
reasons why Btrfs works better in this project compared to ZFS
  1. Btrfs is GPL licensed so it can be included in the vanilla Linux kernel. Many people circumvent this restriction
     by patching the kernel in-house. This is not a scalable solution and it prevents the possibility of redistributing
     the linux kernel.
  2. Btrfs allows the admin to remove disks from a running filesystem. This is important because it allows the admin
     to initially overcommit storage to virtual machines and then later reduce the available storage once the total
     storage requirement is determined. With the ability to reduce the total available storage in a pool, the admin
     can turn off unused disks to save power and dedicate them as spare disks. The admin can also replace the spare
     disks with another set of disks to form a new storage pool and slowly transition volumes from the old pool to the
     new pool.

There are many arguments floating on the internet on the stability of the Btrfs filesystem. The fact of the matter is
that no software is 100% error free and it is always important to take preventive measures against filesystem
corruptions by making frequent backups. If an error is observed in the filesystem code, we can make contributions to it
or report it to the maintainers. Opting to use an alternative filesystem that had more time to mature may seem like a
better route but it reduces the testing done on newer filesystems, like Btrfs. It is more beneficial for the community
as a whole to use Btrfs filesystem and address any potential problems.

## Disk redundancy: RAID-10
Disk failures are inevitable so a redundant disk array is a must have to ensure uninterrupted operations. The list of
RAID levels that provide redundancy are as follows:
 - RAID 1 (mirror)
 - RAID 10 (mirror and stripe)
 - RAID 5 (stripe with single parity)
 - RAID 6 (stripe with double parity)

### RAID 5
RAID 5 provides fault tolerance for a single disk failure but the efficiency of the array dramatically drops after a
disk failure and especially during a resilver. If the storage server is to provide a consistent I/O bandwidth for the
virtual machines even during a disk recovery, this is not an acceptable RAID level.

### RAID 6
When a new disk replaces the damaged disk in a RAID 5 array, the resilver process taxes the other disks so much that
there is a high possibility for another disk to fail as well, which would yield two disk failures. If there are two
failed disks in a RAID 5 array, the entire array is irrecoverable and this is where RAID 6 comes in. RAID 6 provides
fault tolerance for two disk failures but it suffers from the same performance problems as RAID 5. We cannot use
RAID 6 since we cannot guarantee a consistent I/O bandwidth.

### RAID 1
In a RAID 1 array, every block of data is copied to each disk. The Btrfs implementation of RAID 1 is somewhat different
in that it keeps only two copies of the block across the array. For the sake of simplicity, let us continue discussing
the Btrfs implementation of RAID 1. If a disk was to fail, the array will continue to run in degraded mode but with no
performance drop, since the missing data does not have to be reconstructed from all the other disks like a parity based
RAID array. During the resilver process, the I/O taxed onto each disk will be inverse proportional to the number of
disks in the array. This is significantly less than the I/O taxed to each disk in a parity based RAID array, which
requires a complete disk read from every disk in the array. Because the performance degradation is so minimal in this
RAID level, RAID 1 is a good choice when we need to guarantee a consistent I/O bandwidth.

### RAID 10
RAID 10 offers a similar protection to RAID 1 and the disk utilization is also the same but it incorporates block
striping across the array. This effectively improves the I/O performance without costing us reliablility or disk
utilization. It's true that compared to RAID 5 and RAID 6, RAID 1 and RAID 10 requires more disk space to store the
same amount of data and thus effectivly offers less disk utilization. On the flip side, it is more important to provide
a consistent I/O bandwidth than to worry about disk utilization, especially during a disaster recovery situation.

## RAID implementation: Btrfs
Hardware RAID controllers can provide a very nice abstraction of the RAID array from the operating system. In one way,
this benefits the operating system because it no longer needs to independently interface with each disk in the array.
This is especially beneficial for parity based RAID levels since the kernel does not have to compute parity values in
the CPU and the task is offloaded onto the RAID controller.

The same benefit has its drawbacks. Because the operating system lost the ability to interface with each disk
independently, it can no longer retrieve multiple versions of the same block of data from different disks. Normally
there is no need to read the same block multiple times but if the filesystem driver notices a corruption in the first
read operation, it can retry the read of the same block from the other disk to fix a potential bit rot corruption. This
is one huge benefit for using a RAID implementation that is provided by the filesystem driver as opposed to an
implementation that is hardware based. For non-parity based RAID arrays, the CPU requirement is minimal since the
parity values need not be computed for every block. This further lessens the need for a hardware based RAID controller.


