import React, { useEffect, useState } from "react";
import {
    clearPlayerTag,
    getPlayerTag,
    setPlayerTag,
    subscribePlayerTag,
} from "../utils/playerTag";

export default function PlayerTagInput() {
    const [value, setValue] = useState(getPlayerTag() || "");

    // Stay in sync if another component clears or sets the tag.
    useEffect(() => subscribePlayerTag(() => setValue(getPlayerTag() || "")), []);

    const commit = () => {
        if (value.trim()) {
            setPlayerTag(value);
        } else {
            clearPlayerTag();
        }
    };

    return (
        <input
            type="text"
            className="form-control form-control-sm"
            style={{ maxWidth: "10rem" }}
            placeholder="#YOURTAG"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onBlur={commit}
            onKeyDown={(e) => {
                if (e.key === "Enter") {
                    e.preventDefault();
                    commit();
                    e.target.blur();
                }
            }}
            aria-label="Player tag"
        />
    );
}
