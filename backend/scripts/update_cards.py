# Local imports
from apis.utils.db_utils import make_connection
from scripts.utils.data_utils import (
    _parse_battle_time,
    _resolve_rank,
    get_battlelog_data,
    infer_deck,
    insert_battle,
    refresh_cards_catalog,
    upsert_deck,
    upsert_player,
)

RANKED = "pathOfLegend"


def ingest_battles(player_count: int = 100):
    refresh_cards_catalog()
    battlelog_data, rank_by_tag = get_battlelog_data(player_count)

    with make_connection() as connection:
        with connection.cursor() as cursor:
            for battlelog in battlelog_data:
                if not isinstance(battlelog, list):
                    continue
                for battle in battlelog:
                    if battle.get("type") != RANKED:
                        continue
                    team = (battle.get("team") or [None])[0]
                    opp = (battle.get("opponent") or [None])[0]
                    if not team or not opp:
                        continue
                    try:
                        team_deck = infer_deck(team["cards"])
                        opp_deck = infer_deck(opp["cards"])
                        team_deck_id = upsert_deck(cursor, team_deck)
                        opp_deck_id = upsert_deck(cursor, opp_deck)
                        upsert_player(cursor, team["tag"], team.get("name"))
                        if opp.get("tag"):
                            upsert_player(cursor, opp["tag"], opp.get("name"))
                        insert_battle(
                            cursor,
                            timestamp=_parse_battle_time(battle["battleTime"]),
                            team_tag=team["tag"],
                            opp_tag=opp.get("tag"),
                            team_deck_id=team_deck_id,
                            opp_deck_id=opp_deck_id,
                            team_rank=_resolve_rank(team, rank_by_tag),
                            opp_rank=_resolve_rank(opp, rank_by_tag),
                            team_crowns=team.get("crowns"),
                            opp_crowns=opp.get("crowns"),
                        )
                    except (KeyError, ValueError):
                        continue
            connection.commit()


if __name__ == "__main__":
    ingest_battles(player_count=1000)
    print("Cards catalog refreshed and battles ingested.")
