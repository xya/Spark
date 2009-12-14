/*
 Copyright (C) 2009 Pierre-André Saulais <pasaulais@free.fr>

 This file is part of the Spark File-transfer Tool.

 Spark is free software; you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation; either version 2 of the License, or
 (at your option) any later version.

 Spark is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with Spark; if not, write to the Free Software
 Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
*/

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <time.h>

#define BUFFER_SIZE (4096 * 1)

typedef struct
{
    char msg_size[4];
    char msg_type;
    uint8_t blob_type;
    uint16_t transfer_id;
    uint32_t block_id;
    uint16_t block_size;
} BlockHeader;

size_t send_file(int w, char *src_file);
size_t receive_file(int r, char *dst_file);
void set_msg_size(BlockHeader *bh);

int main(int argc, char **argv)
{
    char dst_file[256];
    pid_t pid;
    int p[2];
    size_t sent, received;
    clock_t start, duration;
    double sec, speed;
    
    if(argc < 2)
    {
        printf("Usage: %s <file>\n", argv[0]);
        return 1;
    }
    snprintf(dst_file, sizeof(dst_file), "%s.1", argv[1]);
    
    pipe(p);
    pid = fork();
    if(pid == 0)
    {
        close(p[0]);
        sent = send_file(p[1], argv[1]);
        close(p[1]);
    }
    else if(pid < 0)
    {
        perror("fork() failed");
        return 1;
    }
    else
    {
        start = clock();
        close(p[1]);
        received = receive_file(p[0], dst_file);
        close(p[0]);
        duration = clock() - start;
        sec = ((double)duration / (double)CLOCKS_PER_SEC);
        speed = ((double)received / (1024.0 * 1024.0)) / sec;
        printf("Sent %zi bytes in %f seconds (%f MiB/s)\n", received, sec, speed);
    }
    return 0;
}

size_t send_file(int w, char *src_file)
{
    BlockHeader bh;
    uint32_t blockID = 0;
    char buffer[BUFFER_SIZE];
    int readBytes;
    size_t sent = 0;
    int r = open(src_file, O_RDONLY, 0);
    
    bh.msg_type = '\0';
    bh.blob_type = 1;
    bh.transfer_id = 0;
    while(1)
    {
        readBytes = read(r, buffer, sizeof(buffer));
        if(readBytes == 0)
            break;
        bh.block_id = blockID++;
        bh.block_size = readBytes;
        set_msg_size(&bh);
        write(w, &bh, sizeof(BlockHeader));
        write(w, buffer, readBytes);
        sent += (size_t)readBytes;
    }
    close(r);
    return sent;
}

#define min(a, b) ((a) < (b)? (a) : (b))

size_t receive_file(int r, char *dst_file)
{
    BlockHeader bh;
    char buffer[BUFFER_SIZE];
    int readBytes;
    size_t received = 0;
    int w = open(dst_file, O_WRONLY | O_CREAT | O_TRUNC, 0666);
    
    while(1)
    {
        readBytes = read(r, &bh, sizeof(BlockHeader));
        if(readBytes == 0)
            break;
        readBytes = read(r, buffer, min(bh.block_size, sizeof(buffer)));
        if(readBytes < bh.block_size)
        {
            fprintf(stderr, "Pipe was closed while receiving a block\n");
            break;
        }
        write(w, buffer, bh.block_size);
        received += bh.block_size;
    }
    close(w);
    return received;
}

void set_msg_size(BlockHeader *bh)
{
    size_t textSize = sizeof(bh->msg_size);
    int size = sizeof(*bh) - textSize + bh->block_size;
    if((size < 0x0000) && (size > 0xffff))
        size = 0;
    sprintf(bh->msg_size, "%04x", size);
}