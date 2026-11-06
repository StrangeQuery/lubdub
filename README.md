# xtrack

`xtrack`, `lub` and `dub` play sound that a CARDIAC decodes. The CARDIAC does all of the decoding arithmetic for
every sample: every prediction, every correction and every carry. The host only feeds it cards and passes its
output on to the speakers. It works in three steps:

1. `xtrack` encodes one channel of audio into a track, which is a file of CARDIAC cards. You do this once, ahead of
   time.
2. `lub` plays one channel and `dub` plays two (stereo). For each channel, they run the decoder,
   [`audio/decode.cq`](audio/decode.cq), on a CARDIAC, and they give it the track's cards one at a time, whenever
   one of its INP instructions asks for a card.
3. The decoder outputs each sample as two values: first the thousands, then the units. It has to, because a single
   value from -999 to 999 doesn't have enough levels for good sound. `lub` and `dub` join each pair back into a
   16-bit sample, and write the samples out a block at a time (64 samples, about a millisecond of sound), as soon
   as each block is decoded.

Here is how to get from a wav file to your speakers, using `ffmpeg` to read the audio and `ffplay` to play it:

    ffmpeg -i song.wav -af 'pan=mono|c0=c0' -ar 48000 -f s16le - | xtrack > song.left.track
    ffmpeg -i song.wav -af 'pan=mono|c0=c1' -ar 48000 -f s16le - | xtrack > song.right.track

    lub song.left.track | ffplay -nodisp -autoexit -f s16le -ar 48000 -ch_layout mono -
    dub song.left.track song.right.track | ffplay -nodisp -autoexit -f s16le -ar 48000 -ch_layout stereo -

The first two commands make the tracks for the left and right channels. The last two play them, in mono and in
stereo. The samples come out raw, as signed 16-bit little-endian numbers with no header, so you have to tell the
player what they are: `-f s16le` for the format, `-ar 48000` for the sample rate the audio was encoded at, and mono
or stereo. To save the result as a wav file instead of playing it:

    dub song.left.track song.right.track | ffmpeg -f s16le -ar 48000 -ac 2 -i - song.cardiac.wav

The encoding is a form of ADPCM designed around CARDIAC's decimal arithmetic. The audio is split into blocks of 64
samples, and each block has a step size of M x 10^K. For each sample, the decoder predicts the next value from a
straight line through the previous two samples, and the track's card for that sample says how far to correct the
prediction, as a three-digit code times the step size. Decoding takes about 40 instructions per sample, which is
about 2 million instructions per second for one channel at 48 kHz. [docs/AUDIO.md](docs/AUDIO.md) explains how we
built it and why it has to work this way. To watch the decoder at work, [audio/](audio/) has a 133-card excerpt of
The Blue Danube that is short enough to step through in `ekg` or Cardigan.

To decode tracks in your own Rust program, use the library: `xtrack::Channel` decodes one track and
`xtrack::Stereo` decodes two, a block of 64 samples at a time. They are the same code `lub` and `dub`
run:

```rust
use heartburn::tape;

let left = tape::values(&std::fs::read_to_string("song.left.track")?)?;
let right = tape::values(&std::fs::read_to_string("song.right.track")?)?;
let mut stereo = xtrack::Stereo::new(left.into_iter(), right.into_iter());
while let Some(block) = stereo.next_block().map_err(|(side, e)| format!("{side:?} track: {e}"))? {
    for [left, right] in block {
        // two 16-bit samples, decoded by the two CARDIACs
    }
}
```

## What's in this repo

| | | resembles |
|---|---|---|
| [`xtrack`](#xtrack) | encodes a channel of audio into a track for a CARDIAC to decode | `lame`, `flac` |
| [`lub`](#lub) | decodes a track on a CARDIAC and outputs the audio samples | `flac -d`, `mpg123` |
| [`dub`](#dub) | decodes two tracks, left and right, each on its own CARDIAC, and outputs stereo | `flac -d`, `mpg123` |

All of the commands follow the GNU conventions. They have `--help` and `--version`, short and long options, and
`--` to mark the end of the options. A file named `-` means standard input. Errors look like `PROG: message`, or
`FILE:LINE:COLUMN: error: message` when they point at a line. The exit status is 0 for success, 1 for failure and
2 for a mistake on the command line.

## Install

Currently no binaries are shipped. If you have [Rust](https://rustup.rs) installed, you can build them from the
source code. Cargo fetches heartburn, the CARDIAC engine from [cardiaq](https://github.com/StrangeQuery/cardiaq),
by itself:

    git clone https://github.com/StrangeQuery/xtrack
    cd xtrack
    cargo build --release

The commands end up in `target/release/`. Put that folder on your PATH.

## xtrack

`xtrack` encodes one channel of audio into a track for the decoder.

**Input.** `xtrack` reads raw audio: nothing but the samples for one channel, one after another, each a signed
16-bit little-endian number. There is no header, so nothing in the file says what the sample rate is. We give such
files the extension `.s16` (signed, 16 bits), but that's only a naming convention. You can make one from almost
any audio file with `ffmpeg`. This takes the left channel of `song.wav` at 48 kHz:

    ffmpeg -i song.wav -af 'pan=mono|c0=c0' -ar 48000 -f s16le song.left.s16

Use `c0=c1` instead of `c0=c0` to take the right channel. Any sample rate works, but because the rate isn't recorded
anywhere, you have to give it to the player later.

Then encode the samples, either from the file or straight from `ffmpeg` through a pipe:

    xtrack song.left.s16 > song.left.track
    ffmpeg -i song.wav -af 'pan=mono|c0=c0' -ar 48000 -f s16le - | xtrack > song.left.track

**Output.** The track goes to standard output, one card per line. Each block of 64 samples starts with two cards,
K and M, which give the block's step size. Then come 64 cards, one per sample, each a code from -500 to 499. The
last card is -1, which marks the end. For each block, `xtrack` takes the smallest step size that reaches as far as
the block strays from the prediction. It chooses each code to match the sample the decoder will actually produce, so small errors don't
add up over time. It encodes 32 seconds of audio in a few hundredths of a second.

| | |
|---|---|
| `-h`, `--help` | display help and exit |
| `--version` | output version information and exit |

The exit status is 0 if the track was written. It is 1 if the samples can't be read, if there is an odd number of
bytes, or if the track can't be written. It is 2 if there is a mistake on the command line.

## lub

`lub` plays one channel. A single CARDIAC runs the decoder on the track, and `lub` writes the samples to standard
output a block at a time, as soon as the CARDIAC has decoded each block.

    lub song.left.track | ffplay -nodisp -autoexit -f s16le -ar 48000 -ch_layout mono -
    xtrack < song.left.s16 | lub | ffplay ...    # the track can also come from standard input

**Output.** Raw samples, as signed 16-bit little-endian numbers, in mono. `lub` won't write them to a terminal, so
pipe them to a player or into a file. If the player stops reading, `lub` stops too, without an error.

**Errors.** When something is wrong, `lub` stops with a message instead of playing noise. That happens if the track
ends without its end card, if a line isn't a card (the message gives the line number), or if the decoder's two
values for a sample don't make a 16-bit number.

| | |
|---|---|
| `-h`, `--help` | display help and exit |
| `--version` | output version information and exit |

The exit status is 0 if the track was played to the end, or if the player stopped reading. It is 1 if the track
can't be read or the decoder can't decode it. It is 2 if there is a mistake on the command line.

## dub

`dub` plays stereo. It takes two tracks, one for the left channel and one for the right, and each one is decoded by
its own CARDIAC.

    dub song.left.track song.right.track | ffplay -nodisp -autoexit -f s16le -ar 48000 -ch_layout stereo -
    xtrack < song.left.s16 | dub - song.right.track | ffplay ...    # one of the tracks can come from standard input

**How it works.** The two CARDIACs take turns on a single thread, one block at a time. First the left CARDIAC is
given the next 66 cards of its track (one header and 64 codes), and it runs until it asks for more cards. Then the
right CARDIAC does the same. Each channel's pairs of values are joined into samples, and `dub` writes them in the
order left, right, left, right, which is what a stereo stream is. All of this is `xtrack::Stereo`, which
your own programs can use too.

**Output.** Raw samples, as signed 16-bit little-endian numbers, in stereo, with the left sample first. As with
`lub`, it won't write to a terminal, and if the player stops reading, `dub` stops too.

**Errors.** `dub` reports the same errors as `lub`, and says which track each one is in. It also reports one more:
if the two tracks are different lengths, it says which one is longer and by how many samples, instead of playing one
channel on its own.

| | |
|---|---|
| `-h`, `--help` | display help and exit |
| `--version` | output version information and exit |

The exit status is 0 if both tracks were played to the end, or if the player stopped reading. It is 1 if a track
can't be read, if the decoder can't decode it, or if the two tracks are different lengths. It is 2 if there is a
mistake on the command line.

## License

MIT.
