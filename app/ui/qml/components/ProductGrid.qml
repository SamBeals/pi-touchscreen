import QtQuick
import SellMate 1.0

GridView {
    id: root
    clip: true
    cellWidth: width / Math.max(1, App.browseColumns)
    // Nearly square retail tiles
    cellHeight: Math.max(Theme.cardMinHeight, cellWidth * 1.15)
    model: CatalogModel
    boundsBehavior: Flickable.StopAtBounds
    cacheBuffer: cellHeight * 4

    delegate: Item {
        width: root.cellWidth
        height: root.cellHeight

        ProductCard {
            anchors.fill: parent
            anchors.margins: Math.max(8, Theme.gap / 2)
            slotId: model.slotId
            name: model.name
            priceText: model.priceText
            stockText: model.stockText
            imageUrl: model.imageUrl
            qty: model.qty
        }
    }

    EmptyState {
        anchors.centerIn: parent
        visible: root.count === 0
        message: "No products available right now"
    }

    onWidthChanged: App.setBrowseViewportWidth(Math.round(width))
    Component.onCompleted: App.setBrowseViewportWidth(Math.round(width))
}
