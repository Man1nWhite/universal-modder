-- The Bunny asset replacement uses OfficeSuite's own arms. Keep the selected
-- gloves, but never spawn the separate vanilla hnd_forearms over those arms.
Hooks:PostHook(BlackMarketTweakData, "init", "OfficeSuiteBunnyForearmFix", function(self)
    local style = self.player_styles and self.player_styles.bunny
    if style then
        style.glove_adapter = false
    end
    -- Vanilla and BeardLib both use this list. Avoid touching other outfits.
    local adapter = self.glove_adapter
    local excluded = adapter and adapter.player_style_exclude_list
    if excluded then
        for _, id in pairs(excluded) do
            if id == "bunny" then return end
        end
        table.insert(excluded, "bunny")
    end
end)
