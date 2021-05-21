#!/usr/bin/perl
use Socket;
use POSIX;
use strict;
use Time::Piece;
use Time::HiRes qw(gettimeofday);
my ($verbose, $syncFile);
use Getopt::Long;
Getopt::Long::Configure("bundling", "no_ignore_case", "pass_through");
GetOptions("v!"  => \$verbose,
	   "f:s" => \$syncFile);

$SIG{TERM} = sub { POSIX::_exit(0); };
my ($listen_port, $expected_clients, $syncCount) = @ARGV;
if (! $syncCount) {
    $syncCount = 1;
}
sub timestamp($) {
    my ($str) = @_;
    my (@now) = gettimeofday();
    printf STDERR  "sync %s.%06d %s\n", gmtime($now[0])->strftime("%Y-%m-%dT%T"), $now[1], $str;
}
timestamp("Clusterbuster sync starting");
my $sockaddr = "S n a4 x8";
socket(SOCK, AF_INET, SOCK_STREAM, getprotobyname('tcp')) || die "socket: $!";
$SIG{TERM} = sub { close SOCK; POSIX::_exit(0); };
setsockopt(SOCK,SOL_SOCKET, SO_REUSEADDR, pack("l",1)) || die "setsockopt reuseaddr: $!\n";
setsockopt(SOCK,SOL_SOCKET, SO_KEEPALIVE, pack("l",1)) || die "setsockopt keepalive: $!\n";
bind(SOCK, pack($sockaddr, AF_INET, $listen_port, "\0\0\0\0")) || die "bind: $!\n";
my $mysockaddr = getsockname(SOCK);
my ($junk, $port, $addr) = unpack($sockaddr, $mysockaddr);
die "can't get port $port: $!\n" if ($port ne $listen_port);
my (@clients);

my ($tmpSyncFile) = (defined($syncFile) && $syncFile ne '') ? "${syncFile}.tmp" : undef;

while ($syncCount < 0 || $syncCount-- > 0) {
    my $child = fork();
    if ($child == 0) {
	timestamp("Listening on port $listen_port");
	listen(SOCK, 5) || die "listen: $!";
	print STDERR "Expect $expected_clients clients\n";
	while ($expected_clients > 0) {
	    my ($client);
	    accept($client, SOCK) || next;
	    my $peeraddr = getpeername($client);
	    my ($port, $addr) = sockaddr_in($peeraddr);
	    my $peerhost = gethostbyaddr($addr, AF_INET);
	    my $peeraddr = inet_ntoa($addr);
	    my ($tbuf) = "NULL";
	    if (sysread($client, $tbuf, 1024) <= 0) {
		timestamp("Read token from $peerhost failed: $!");
	    }
	    timestamp("Accepted connection from $peerhost ($peeraddr) on $port, token $tbuf");
	    if ($tbuf =~ /,STATS,/ && defined $tmpSyncFile) {
		chomp $tbuf;
		open SYNC, ">>", "$tmpSyncFile" || die("Can't open sync file $tmpSyncFile: $!\n");
		print SYNC "$tbuf\n";
		close SYNC || die "Can't close sync file: $!\n";
	    }
	    push @clients, $client;
	    $expected_clients--;
	}
	timestamp("Waiting 1 second to sync:");
	sleep(1);
	timestamp("Done!");
        POSIX::_exit(0);
    } elsif ($child < 1) {
        timestamp("Fork failed: $!");
	POSIX::_exit(1);
    } else {
        wait();
    }
}
if (defined $syncFile && $syncFile ne "" && -f $tmpSyncFile) {
    rename($tmpSyncFile, $syncFile) || die "Can't rename $syncFile to $tmpSyncFile: $!\n";
    timestamp("Waiting for sync file $syncFile to be removed");
    while (-f $syncFile) {
	sleep(5);
    }
    timestamp("Sync file $syncFile removed, exiting");
}

POSIX::_exit(0);
EOF
