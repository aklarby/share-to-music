-- Arguments are passed as data, never interpolated into AppleScript source.
on run argv
    set audioFile to POSIX file (item 1 of argv) as alias
    set marker to item 2 of argv
    tell application "Music"
        with timeout of 150 seconds
            -- The marker is embedded in the M4A before import. It survives copying
            -- into Music's media folder and makes a retry after interruption safe.
            -- Music's indexed search avoids reading comments for every library
            -- track. Verify the exact marker because search can return partial hits.
            set matches to search library playlist 1 for marker only all
            repeat with candidate in matches
                if comment of candidate is marker then
                    return persistent ID of candidate
                end if
            end repeat
            set addedTracks to add {audioFile}
            if class of addedTracks is list then
                if (count of addedTracks) = 0 then error "Music did not add the audio file."
                set addedTrack to item 1 of addedTracks
            else
                set addedTrack to addedTracks
            end if
            -- The comment was embedded by FFmpeg. Rewriting it after add can
            -- fail with -54 while Music copies/uploads the new track.
            return persistent ID of addedTrack
        end timeout
    end tell
end run
