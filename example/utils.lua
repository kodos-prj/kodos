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

return {
    dumpTable = dumpTable
}