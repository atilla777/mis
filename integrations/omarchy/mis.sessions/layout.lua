-- Loaded explicitly by the user; applies only to the pult's named workspaces.
-- Uses the custom-layout API shipped in Hyprland 0.56.2.
if _G.mis_sessions_layout_loaded then return end

hl.layout.register("mis-sessions", {
  recalculate = function(ctx)
    local n = #ctx.targets
    if n == 0 then return end
    local cols = n == 1 and 1 or 2
    for i, target in ipairs(ctx.targets) do
      target:place(ctx:grid_cell(i, cols))
    end
  end,
})

hl.workspace_rule({
  workspace = "n[s:mis-]",
  layout = "lua:mis-sessions",
})

hl.window_rule({
  match = { class = "^mis[.]sessions[.].*$" },
  no_initial_focus = true,
  group = "barred",
  tile = true,
})

_G.mis_sessions_layout_loaded = true
