-- Arguments are passed as data, never interpolated into AppleScript source.
on run argv
    set audioFile to POSIX file (item 1 of argv) as alias
    set marker to item 2 of argv
    tell application "Music"
        with timeout of 150 seconds
            -- The marker is embedded in the M4A before import. It survives copying
            -- into Music's media folder and makes a retry after interruption safe.
            set matches to (every file track of library playlist 1 whose comment is marker)
            if (count of matches) > 0 then
                return persistent ID of item 1 of matches
            end if
            set addedTracks to add {audioFile}
            if class of addedTracks is list then
                if (count of addedTracks) = 0 then error "Music did not add the audio file."
                set addedTrack to item 1 of addedTracks
            else
                set addedTrack to addedTracks
            end if
            set comment of addedTrack to marker
            return persistent ID of addedTrack
        end timeout
    end tell
end run
