-- Utility functions

function dumpTable(tbl, indent)
    indent = indent or 0
    for k, v in pairs(tbl) do
        print(string.rep(" ", indent) .. tostring(k) .. ":")
        if type(v) == "table" then
            dumpTable(v, indent + 2)
        else
            print(string.rep(" ", indent + 2) .. tostring(v))
        end
    end
end

function list(l)
    return setmetatable(l, {
        __tostring = function(t)
            res = ''
            for k, v in pairs(t) do res = res .. '\'' .. v .. '\' ' end
            return res
        end,
        __concat = function(x, y)
            for _, v in ipairs(y) do table.insert(x, v) end
            return x
        end
    })
end

function map(m)
    return setmetatable(m, {
        __tostring = function(t)
            res = ''
            for k, v in pairs(t) do res = res .. '(' .. k .. ',' .. tostring(v) .. ') ' end
            return res
        end,
        __concat = function(x, y)
            for k, v in pairs(y) do rawset(x, k, v) end
            return x
        end
    })
end

function if_true(cond, m)
    if cond then
        return m
    end
    if type(m) == "table" then
        return {}
    end
    return nil
end

function if_else(cond, m_true, m_false)
    if cond then
        return m_true
    end
    return m_false
end

local function _make_list(repo_info, items, count)
    local t = {}
    for i = 1, count do
        t[i] = items[i]
    end

    return setmetatable(t, {
        __concat = function(a, b)
            local merged = {}
            local n = 0
            for _, pkg in ipairs(a) do
                n = n + 1; merged[n] = pkg
            end
            for _, pkg in ipairs(b) do
                n = n + 1; merged[n] = pkg
            end

            -- Merged list loses single-repo identity; store nil source
            return _make_list(nil, merged, n)
        end,

        __len = function(self)
            return #self
        end,

        __tostring = function(self)
            local parts = {}
            for i, pkg in ipairs(self) do parts[i] = pkg.name end
            return "{" .. table.concat(parts, ", ") .. "}"
        end,
    })
end

return {
    dumpTable = dumpTable,
    list = list,
    map = map,
    if_true = if_true,
    if_else = if_else,
    _make_list = _make_list,
}
