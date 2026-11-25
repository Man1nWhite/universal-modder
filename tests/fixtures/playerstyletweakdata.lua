function BlackMarketTweakData:get_player_style_value(player_style, character_name, key)
	if key == nil then
		return
	end

	player_style = player_style or "none"
	local data = self.player_styles[player_style]

	if data == nil then
		return nil
	end

	character_name = CriminalsManager.convert_old_to_new_character_workname(character_name)
	local character_value = data.characters and data.characters[character_name] and data.characters[character_name][key]

	if character_value ~= nil then
		return character_value
	end

	local tweak_value = data and data[key]

	return tweak_value
end

function BlackMarketTweakData:get_suit_variation_value(player_style, material_variation, character_name, key)
	if key == nil then
		return nil
	end

	player_style = player_style or "none"
	material_variation = material_variation or "default"
	local data = self.player_styles[player_style]
	local variation_data = data and data.material_variations and data.material_variations[material_variation]

	if variation_data == nil then
		return nil
	end

	character_name = CriminalsManager.convert_old_to_new_character_workname(character_name)
	local character_material_variations = data.characters and data.characters[character_name] and data.characters[character_name].material_variations
	local character_value = character_material_variations and character_material_variations[material_variation] and character_material_variations[material_variation][key]

	if character_value ~= nil then
		return character_value
	end

	local tweak_value = variation_data and variation_data[key]

	return tweak_value
end
